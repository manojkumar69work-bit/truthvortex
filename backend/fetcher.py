"""HTTP fetching for the scraper: per-domain pacing + bot-wall fallback.

Every outbound page/feed request in scraper.py goes through :func:`get` so that
two behaviours are enforced in one place:

  1. PER-DOMAIN PACING (``PER_DOMAIN_DELAY_SECONDS``)
     Feeds are fetched from a ThreadPoolExecutor (MAX_CONCURRENT_SOURCES), and
     several SOURCES entries can share one publisher host. Without a per-host
     floor, that publisher gets several simultaneous hits and starts 429ing.
     The delay is per *host*, not global, so unrelated publishers still overlap.

  2. IMPERSONATE FALLBACK (``ENABLE_IMPERSONATE_FALLBACK``)
     Some CDNs block on TLS/HTTP2 fingerprint, not on headers. ESPNcricinfo's
     Akamai returns 403 to python-requests and 200 to curl with byte-identical
     headers, so no amount of header tuning fixes it. On a bot-wall status
     (403/429/503) we retry once through curl_cffi, which presents a real Chrome
     fingerprint. This is failure-triggered only — the happy path never pays for
     it, and with the flag off the module behaves exactly like plain requests.

curl_cffi is imported lazily: if the wheel is missing the fallback disables
itself with one warning instead of breaking every fetch. Failures from the
fallback are re-raised as ``requests.exceptions.RequestException`` subclasses so
callers only ever need to catch the requests exception hierarchy.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from urllib.parse import urlparse

import requests

logger = logging.getLogger("truthvortex.fetcher")
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(_handler)
    logger.setLevel(os.getenv("LOG_LEVEL", "INFO").upper())
    logger.propagate = False


# =========================
# CONFIG
# =========================
PER_DOMAIN_DELAY_SECONDS = float(os.getenv("PER_DOMAIN_DELAY_SECONDS", "0"))

ENABLE_IMPERSONATE_FALLBACK = (
    os.getenv("ENABLE_IMPERSONATE_FALLBACK", "false").lower() == "true"
)

# curl_cffi browser profile. "chrome" tracks the newest Chrome build the
# installed curl_cffi knows about, which is what we want against fingerprint
# checks — pinning an old build is what gets a profile blocklisted.
IMPERSONATE_PROFILE = os.getenv("IMPERSONATE_PROFILE", "chrome")

# Statuses that mean "a bot wall answered", not "the resource is gone".
# 404/410/500 are NOT here: retrying those with a different fingerprint just
# burns a second request for the same answer.
BOT_WALL_STATUSES = frozenset({403, 429, 503})


# =========================
# PER-DOMAIN THROTTLE
# =========================
_throttle_lock = threading.Lock()
_last_request_at: dict[str, float] = {}


def _host_of(url: str) -> str:
    try:
        return (urlparse(url).netloc or "").lower()
    except Exception:
        return ""


def _throttle(url: str) -> None:
    """Block until ``PER_DOMAIN_DELAY_SECONDS`` has passed since this host's last hit.

    The sleep happens outside the lock — holding it across the sleep would
    serialise every worker behind the slowest host and undo the concurrency.
    """
    if PER_DOMAIN_DELAY_SECONDS <= 0:
        return

    host = _host_of(url)
    if not host:
        return

    while True:
        with _throttle_lock:
            now = time.monotonic()
            earliest = _last_request_at.get(host, 0.0) + PER_DOMAIN_DELAY_SECONDS

            if now >= earliest:
                # Claim the slot while still holding the lock, so two threads
                # can't both decide they are clear to go.
                _last_request_at[host] = now
                return

            wait_for = earliest - now

        time.sleep(wait_for)


# =========================
# SESSION REUSE
# =========================
# requests.Session is not documented as thread-safe, and feeds are fetched from
# a thread pool, so each worker keeps its own session (and its own connection
# pool / keep-alive) instead of sharing one.
_local = threading.local()


def _session() -> requests.Session:
    session = getattr(_local, "session", None)

    if session is None:
        session = requests.Session()
        _local.session = session

    return session


# =========================
# IMPERSONATE FALLBACK
# =========================
_impersonate_lock = threading.Lock()
_impersonate_requests = None  # curl_cffi.requests module, or False once known bad

stats = {"requests": 0, "bot_walled": 0, "impersonated": 0, "impersonate_ok": 0}
_stats_lock = threading.Lock()


def _bump(key: str) -> None:
    with _stats_lock:
        stats[key] = stats.get(key, 0) + 1


def _curl_requests():
    """Import curl_cffi.requests once. Returns the module, or None if unavailable."""
    global _impersonate_requests

    with _impersonate_lock:
        if _impersonate_requests is None:
            try:
                from curl_cffi import requests as curl_requests

                _impersonate_requests = curl_requests
            except Exception as exc:  # noqa: BLE001 - any import failure disables it
                logger.warning(
                    "  ! Impersonate fallback unavailable (curl_cffi import failed: %s)."
                    " Bot-walled fetches will keep returning their original status.",
                    exc,
                )
                _impersonate_requests = False

        return _impersonate_requests or None


def _impersonate_get(url: str, headers: dict | None, timeout: float):
    """Re-fetch ``url`` with a real browser TLS fingerprint.

    Raises a ``requests.exceptions`` type on failure so callers written against
    requests keep working unchanged.
    """
    curl_requests = _curl_requests()

    if curl_requests is None:
        return None

    _bump("impersonated")

    try:
        response = curl_requests.get(
            url,
            headers=headers,
            timeout=timeout,
            impersonate=IMPERSONATE_PROFILE,
        )
    except Exception as exc:  # noqa: BLE001 - curl_cffi has its own hierarchy
        message = str(exc).lower()

        if "timed out" in message or "timeout" in message:
            raise requests.exceptions.Timeout(
                f"impersonate fetch timed out: {url}"
            ) from exc

        raise requests.exceptions.RequestException(
            f"impersonate fetch failed: {exc}"
        ) from exc

    # set_response_encoding() looks for apparent_encoding; curl_cffi does not
    # provide it. Feed it curl's own detected charset when we can, so a Telugu
    # feed served as cp1252 is not force-decoded as utf-8.
    if not hasattr(response, "apparent_encoding"):
        try:
            response.apparent_encoding = getattr(response, "charset", None)
        except Exception:  # noqa: BLE001 - read-only/slotted response object
            pass

    return response


# =========================
# PUBLIC API
# =========================
def get(url: str, *, headers: dict | None = None, timeout: float = 12, **kwargs):
    """GET ``url``, paced per host, with an optional bot-wall retry.

    Returns a response object exposing the requests attributes the scraper uses
    (``status_code``, ``text``, ``encoding``, ``raise_for_status``). The
    response is returned unraised — callers still decide whether to call
    ``raise_for_status()``.
    """
    _throttle(url)
    _bump("requests")

    response = _session().get(url, headers=headers, timeout=timeout, **kwargs)

    if response.status_code not in BOT_WALL_STATUSES:
        return response

    _bump("bot_walled")

    if not ENABLE_IMPERSONATE_FALLBACK:
        return response

    logger.info(
        "    [Bot wall %s] retrying %s with %s fingerprint",
        response.status_code,
        _host_of(url) or url,
        IMPERSONATE_PROFILE,
    )

    _throttle(url)
    impersonated = _impersonate_get(url, headers, timeout)

    if impersonated is None:
        return response

    if impersonated.status_code < 400:
        _bump("impersonate_ok")
        return impersonated

    # Still walled. Return the impersonated response rather than the original:
    # it is the more recent answer, and its status is what the caller should log.
    return impersonated


def stats_line() -> str:
    """One-line summary for the end-of-cycle log."""
    with _stats_lock:
        snapshot = dict(stats)

    return (
        f"HTTP: {snapshot['requests']} requests, "
        f"{snapshot['bot_walled']} bot-walled, "
        f"{snapshot['impersonated']} impersonate retries, "
        f"{snapshot['impersonate_ok']} recovered"
    )
