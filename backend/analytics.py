"""First-party, cookie-free analytics.

The browser posts a small beacon to ``POST /track``. Nothing that identifies a
person is stored: the visitor column is a hash of (day, secret salt, IP, user
agent), so the same reader counts once per day and cannot be followed from one
day to the next. Referrers are cut down to their host name. Rows older than
ANALYTICS_RETENTION_DAYS are deleted by the scraper's purge step.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import secrets
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from fastapi import APIRouter, Request, Response

from categories import VALID_CATEGORIES
from db import get_cursor
from security import get_client_ip, limiter

logger = logging.getLogger("red4ce.analytics")

track_router = APIRouter()

EVENT_KINDS = frozenset({"pageview", "article_view", "source_click"})

# Without a configured salt, fall back to one per process: visitor counts then
# reset on every deploy, which undercounts but never leaks a stable hash.
_SALT = os.getenv("ANALYTICS_SALT") or secrets.token_hex(32)

_BOT_RE = re.compile(r"bot|crawl|spider|slurp|preview|headless|lighthouse", re.IGNORECASE)
_TABLET_RE = re.compile(r"ipad|tablet", re.IGNORECASE)
_MOBILE_RE = re.compile(r"mobi|android|iphone", re.IGNORECASE)

_MAX_BODY = 2048


def _device(user_agent: str) -> str:
    if _TABLET_RE.search(user_agent):
        return "tablet"
    if _MOBILE_RE.search(user_agent):
        return "mobile"
    return "desktop"


def _visitor_hash(ip: str, user_agent: str) -> str:
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    raw = f"{day}|{_SALT}|{ip}|{user_agent}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:20]


def _referrer_host(value: Any) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    host = urlparse(value[:500]).hostname
    return host[:100] if host else None


@track_router.post("/track", status_code=204)
# The beacon fires once per page load and once per opened article; 60/min is
# far above a real reader and caps how fast one client can inflate counts.
@limiter.limit("60/minute")
async def track(request: Request) -> Response:
    """Record one analytics event. Always answers 204 so a bad beacon never
    surfaces as an error in the reader's console.

    The body is JSON sent as text/plain: that keeps it a CORS "simple request",
    so the browser skips the preflight round-trip.
    """
    user_agent = request.headers.get("user-agent", "")[:300]
    if not user_agent or _BOT_RE.search(user_agent):
        return Response(status_code=204)

    raw = await request.body()
    if len(raw) > _MAX_BODY:
        return Response(status_code=204)
    try:
        payload = json.loads(raw or b"{}")
    except ValueError:
        return Response(status_code=204)
    if not isinstance(payload, dict):
        return Response(status_code=204)

    kind = payload.get("kind")
    if kind not in EVENT_KINDS:
        return Response(status_code=204)

    article_id = payload.get("article_id")
    if not isinstance(article_id, int) or isinstance(article_id, bool) or article_id <= 0:
        article_id = None

    category = payload.get("category")
    if category not in VALID_CATEGORIES:
        category = None

    path = payload.get("path")
    if not isinstance(path, str) or not path.startswith("/"):
        path = None
    else:
        path = path.split("?")[0][:200]

    try:
        with get_cursor(commit=True) as cur:
            cur.execute(
                "INSERT INTO events (kind, article_id, category, path, referrer, device, visitor) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s);",
                (
                    kind,
                    article_id,
                    category,
                    path,
                    _referrer_host(payload.get("referrer")),
                    _device(user_agent),
                    _visitor_hash(get_client_ip(request), user_agent),
                ),
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning("track insert failed: %s", exc)
    return Response(status_code=204)


def summary(days: int) -> dict[str, Any]:
    """Dashboard numbers for the last ``days`` days (UTC)."""
    window = "ts >= (NOW() AT TIME ZONE 'UTC') - make_interval(days => %s)"
    with get_cursor(dict_rows=True) as cur:
        cur.execute(
            "SELECT "
            "  COUNT(*) FILTER (WHERE kind = 'pageview') AS pageviews, "
            "  COUNT(*) FILTER (WHERE kind = 'article_view') AS article_views, "
            "  COUNT(*) FILTER (WHERE kind = 'source_click') AS source_clicks, "
            "  COUNT(DISTINCT visitor) AS visitors "
            f"FROM events WHERE {window};",
            (days,),
        )
        totals = cur.fetchone()

        cur.execute(
            "SELECT to_char(date_trunc('day', ts), 'YYYY-MM-DD') AS day, "
            "  COUNT(*) FILTER (WHERE kind = 'pageview') AS pageviews, "
            "  COUNT(*) FILTER (WHERE kind = 'article_view') AS article_views, "
            "  COUNT(DISTINCT visitor) AS visitors "
            f"FROM events WHERE {window} "
            "GROUP BY 1 ORDER BY 1;",
            (days,),
        )
        daily = cur.fetchall()

        cur.execute(
            "SELECT e.article_id, n.title, n.source, n.is_original, "
            "  COALESCE(n.category, MAX(e.category)) AS category, COUNT(*) AS views "
            "FROM events e LEFT JOIN news n ON n.id = e.article_id "
            f"WHERE e.kind = 'article_view' AND e.article_id IS NOT NULL AND e.{window} "
            "GROUP BY e.article_id, n.title, n.source, n.is_original, n.category "
            "ORDER BY views DESC LIMIT 15;",
            (days,),
        )
        top_articles = cur.fetchall()

        cur.execute(
            "SELECT category, COUNT(*) AS views FROM events "
            f"WHERE kind = 'article_view' AND category IS NOT NULL AND {window} "
            "GROUP BY category ORDER BY views DESC;",
            (days,),
        )
        categories = cur.fetchall()

        cur.execute(
            "SELECT referrer, COUNT(*) AS visits FROM events "
            f"WHERE kind = 'pageview' AND referrer IS NOT NULL AND {window} "
            "GROUP BY referrer ORDER BY visits DESC LIMIT 10;",
            (days,),
        )
        referrers = cur.fetchall()

        cur.execute(
            "SELECT device, COUNT(DISTINCT visitor) AS visitors FROM events "
            f"WHERE {window} GROUP BY device ORDER BY visitors DESC;",
            (days,),
        )
        devices = cur.fetchall()

        cur.execute(
            "SELECT COUNT(*) AS total, "
            "  COUNT(*) FILTER (WHERE is_original) AS originals, "
            "  COUNT(*) FILTER (WHERE status = 'draft') AS drafts "
            "FROM news;"
        )
        content = cur.fetchone()

        cur.execute(
            "SELECT source, COUNT(*) AS articles FROM news "
            "GROUP BY source ORDER BY articles DESC LIMIT 25;"
        )
        sources = cur.fetchall()

    return {
        "days": days,
        "totals": totals,
        "daily": daily,
        "top_articles": top_articles,
        "categories": categories,
        "referrers": referrers,
        "devices": devices,
        "content": content,
        "sources": sources,
    }
