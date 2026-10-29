"""Request identity, rate limiting, and admin authentication.

Lives outside main.py so the admin router can share the same limiter instance
without a circular import.
"""

from __future__ import annotations

import logging
import os
import secrets
import threading
import time

from fastapi import HTTPException, Request
from slowapi import Limiter

logger = logging.getLogger("red4ce.security")


# ─── Client IP (proxy-aware) ───────────────────────────────────
def get_client_ip(request: Request) -> str:
    """Extract client IP from request, respecting proxy headers.

    Order of precedence:
    1. X-Forwarded-For (first entry)
    2. Forwarded (first entry)
    3. request.client.host (direct connection)
    """
    # X-Forwarded-For: client, proxy1, proxy2
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()

    # Forwarded: for="[2001:db8::1]"
    fwd = request.headers.get("forwarded")
    if fwd:
        for part in fwd.split(";"):
            part = part.strip()
            if part.startswith("for="):
                return part[4:].strip(' "[]')

    # Fallback to direct connection
    return request.client.host if request.client else "unknown"


limiter = Limiter(key_func=get_client_ip, default_limits=["120/minute"])


# ─── Admin auth ────────────────────────────────────────────────
# A short token is guessable no matter how slow the rate limit is, so anything
# under this length is treated the same as no token: the admin API stays shut.
_MIN_TOKEN_LEN = 32

# Per-IP lockout on top of the route rate limits: 5 bad tokens inside 15
# minutes locks that IP out of every admin route for 15 minutes.
_MAX_FAILURES = 5
_FAILURE_WINDOW_S = 15 * 60
_LOCKOUT_S = 15 * 60

_failures: dict[str, list[float]] = {}
_locked_until: dict[str, float] = {}
_auth_lock = threading.Lock()


def _admin_token() -> str:
    return os.getenv("ADMIN_TOKEN", "").strip()


def _record_failure(ip: str, now: float) -> None:
    with _auth_lock:
        recent = [t for t in _failures.get(ip, []) if now - t < _FAILURE_WINDOW_S]
        recent.append(now)
        _failures[ip] = recent
        if len(recent) >= _MAX_FAILURES:
            _locked_until[ip] = now + _LOCKOUT_S
            _failures.pop(ip, None)
            logger.warning("Admin auth: %s locked out after %d failures", ip, len(recent))


def require_admin(request: Request) -> str:
    """FastAPI dependency: allow the request only with the admin bearer token.

    Fails closed. With ADMIN_TOKEN unset (or too short to be safe) every call
    is refused with 503, the same stance /scrape takes. Returns the client IP
    so routes can write it to the audit log.
    """
    expected = _admin_token()
    if len(expected) < _MIN_TOKEN_LEN:
        logger.error(
            "Admin API refused: ADMIN_TOKEN is unset or shorter than %d chars.",
            _MIN_TOKEN_LEN,
        )
        raise HTTPException(status_code=503, detail="Admin API is not configured.")

    ip = get_client_ip(request)
    now = time.time()
    with _auth_lock:
        until = _locked_until.get(ip, 0.0)
        if until > now:
            raise HTTPException(
                status_code=429,
                detail="Too many failed attempts. Try again later.",
                headers={"Retry-After": str(int(until - now) + 1)},
            )
        _locked_until.pop(ip, None)

    token = request.headers.get("authorization", "").removeprefix("Bearer ").strip()
    # Bytes, not str: compare_digest raises TypeError on non-ASCII str input.
    if not secrets.compare_digest(token.encode("utf-8"), expected.encode("utf-8")):
        _record_failure(ip, now)
        raise HTTPException(status_code=401, detail="Unauthorized")

    with _auth_lock:
        _failures.pop(ip, None)
    return ip
