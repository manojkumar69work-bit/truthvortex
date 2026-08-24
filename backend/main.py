"""TruthVortex FastAPI app.

Endpoints:
- GET /            → service banner
- GET /health      → readiness probe
- GET /news        → latest articles
- GET /news/{cat}  → articles in a single category (filtered in SQL)
- GET /search      → ILIKE search across title/summary/source/ai_summary
"""

from __future__ import annotations

import logging
import os
import secrets
import threading
import time
from datetime import timezone
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from dotenv import load_dotenv
from categories import VALID_CATEGORIES, resolve
from db import get_cursor
from source_policy import has_image_risk, is_blocked_source

load_dotenv()

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("truthvortex")

app = FastAPI(title="TruthVortex API")


# ─── Background scraper (runs every 30 min) ───────────────────
_SCRAPER_INTERVAL = int(os.getenv("SCRAPER_INTERVAL_MINUTES", "30")) * 60
_scraper_thread: threading.Thread | None = None
_scraper_stop = threading.Event()


def _run_scraper_loop() -> None:
    from scraper import run_scraper

    while not _scraper_stop.is_set():
        try:
            logger.info("Background scraper starting...")
            run_scraper()
            logger.info("Background scraper finished.")
        except Exception as exc:
            logger.error("Background scraper error: %s", exc)
        _scraper_stop.wait(_SCRAPER_INTERVAL)


def _start_background_scraper() -> None:
    global _scraper_thread
    if os.getenv("DISABLE_BACKGROUND_SCRAPER"):
        logger.info("Background scraper disabled via DISABLE_BACKGROUND_SCRAPER")
        return
    if _scraper_thread is not None and _scraper_thread.is_alive():
        return
    _scraper_thread = threading.Thread(target=_run_scraper_loop, daemon=True)
    _scraper_thread.start()
    logger.info("Background scraper thread started (every %ss).", _SCRAPER_INTERVAL)


# ─── Rate limiting (per-IP, proxy-aware) ────────────────────────────
def _get_client_ip(request: Request) -> str:
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


limiter = Limiter(key_func=_get_client_ip, default_limits=["120/minute"])
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
# slowapi only enforces `default_limits` when this middleware is installed —
# without it the default is dead config and any route without its own
# @limiter.limit decorator is completely unthrottled.
app.add_middleware(SlowAPIMiddleware)


# ─── Security headers ──────────────────────────────────────────
@app.middleware("http")
async def _security_headers(request: Request, call_next):
    response = await call_next(request)
    headers = response.headers
    headers.setdefault("X-Content-Type-Options", "nosniff")
    headers.setdefault("X-Frame-Options", "DENY")
    headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    headers.setdefault("Strict-Transport-Security", "max-age=63072000; includeSubDomains")
    # Allow same-origin scripts/styles for potential /api co-hosting; adjust as needed.
    headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: https:; font-src 'self' data:; frame-ancestors 'none'",
    )
    headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
    return response


# ─── CORS ──────────────────────────────────────────────────────
# Browsers reject allow_origins=["*"] together with allow_credentials=True,
# and "*" is unsafe in production. Require explicit origins.
_cors_origins_raw = os.getenv("CORS_ALLOW_ORIGINS", "http://localhost:3000")
_cors_origins = [o.strip() for o in _cors_origins_raw.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins or ["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["*"],
)


# ─── Schema ────────────────────────────────────────────────────
def ensure_schema() -> None:
    """Create the table and indexes (idempotent).

    Uses a single autocommit connection so there is never an idle-in-transaction
    connection blocking subsequent DDL.  CONCURRENTLY is deliberately omitted
    — at boot there are no concurrent writers.
    """
    from db import get_conn

    with get_conn() as conn:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS news (
                    id SERIAL PRIMARY KEY,
                    source TEXT,
                    title TEXT,
                    title_original TEXT,
                    link TEXT UNIQUE,
                    summary TEXT,
                    ai_summary TEXT,
                    image TEXT,
                    published TIMESTAMP DEFAULT NOW(),
                    category TEXT DEFAULT 'breaking'
                );
                """
            )
            cur.execute(
                "ALTER TABLE news ADD COLUMN IF NOT EXISTS title_original TEXT;"
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS news_published_idx "
                "ON news (published DESC NULLS LAST);"
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS news_category_published_idx "
                "ON news (category, published DESC NULLS LAST);"
            )
            # /news/{category} filters on LOWER(category); a plain-column index
            # can't serve that, so add the matching functional index.
            cur.execute(
                "CREATE INDEX IF NOT EXISTS news_lower_category_published_idx "
                "ON news (LOWER(category), published DESC NULLS LAST);"
            )
            # Trigram index for fuzzy / ILIKE search.
            try:
                cur.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")
                cur.execute(
                    "CREATE INDEX IF NOT EXISTS news_title_trgm_idx "
                    "ON news USING GIN (title gin_trgm_ops);"
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "pg_trgm skipped (search falls back to ILIKE seq scan): %s",
                    exc,
                )


# ─── Row → JSON ────────────────────────────────────────────────
def _row_to_article(row: dict[str, Any]) -> dict[str, Any]:
    category = resolve(stored=row.get("category"), source=row.get("source"))

    # `published` is stored as naive UTC. Serialising it without an offset
    # makes every client guess, and JS `new Date("...T10:00:00")` guesses
    # *local time* — so the same row reads hours off depending on the reader.
    published = row.get("published")
    if published is not None and published.tzinfo is None:
        published = published.replace(tzinfo=timezone.utc)

    # The scraper already drops copyright-risky images at ingest, but rows
    # written before that gate existed can still carry one, so re-check on the
    # way out. Blanking the field makes the client show its own placeholder.
    image = row["image"] or ""
    if image and has_image_risk(row.get("source")):
        image = ""

    return {
        "id": row["id"],
        "source": row["source"],
        "title": row["title"],
        "title_original": row.get("title_original") or "",
        "link": row["link"],
        "summary": row["summary"] or "",
        "image": image,
        "published": published.isoformat() if published else None,
        "category": category,
        "ai_summary": row.get("ai_summary") or "",
    }


def _allowed_articles(rows: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    articles = []
    for row in rows:
        if is_blocked_source(row.get("source")):
            continue
        articles.append(_row_to_article(row))
        if len(articles) >= limit:
            break
    return articles


_SELECT = (
    "id, source, title, title_original, link, summary, image, published, category, ai_summary"
)


# ─── Routes ────────────────────────────────────────────────────
@app.on_event("startup")
def _startup() -> None:
    # Surface obvious misconfiguration early (without logging secret values).
    provider = os.getenv("AI_PROVIDER", "openrouter").strip().lower()
    has_ai_key = bool(
        os.getenv("AI_API_KEY")
        or os.getenv("OPENROUTER_API_KEY")
        or os.getenv("OPENROUTER_API_KEY_2")
        or os.getenv("GROQ_API_KEY")
        or os.getenv("GEMINI_API_KEY")
        or os.getenv("NVIDIA_API_KEY")
        or os.getenv("NVAPI_KEY")
    )
    has_db = bool(os.getenv("DATABASE_URL") or os.getenv("DB_PASSWORD"))

    if not has_db:
        logger.error("CRITICAL: No DATABASE_URL or DB_PASSWORD set. DB will fail.")
        if os.getenv("ENVIRONMENT") == "production":
            raise RuntimeError("DATABASE_URL or DB_PASSWORD is required in production")

    if not has_ai_key:
        logger.error("CRITICAL: No AI API key set for provider '%s'. Summaries will be empty.", provider)
        if os.getenv("ENVIRONMENT") == "production":
            raise RuntimeError(f"AI API key required for provider '{provider}' in production")

    if has_db:
        logger.info("Database configuration: OK")
    if has_ai_key:
        logger.info("AI provider '%s': key configured", provider)
    logger.info("CORS allowed origins: %s", _cors_origins)

    # Don't crash the whole app if the DB is briefly unavailable at boot;
    # /health will report the problem and the platform can retry.
    try:
        ensure_schema()
    except Exception as exc:  # noqa: BLE001
        logger.warning("ensure_schema failed (will retry on demand): %s", exc)

    _start_background_scraper()


@app.on_event("shutdown")
def _shutdown() -> None:
    from db import close_pool

    close_pool()


@app.get("/")
def root() -> dict[str, Any]:
    return {
        "message": "TruthVortex API is running",
        "endpoints": ["/news", "/news/{category}", "/search", "/scrape", "/health"],
    }


@app.get("/health")
@limiter.exempt
def health(response: Response) -> dict[str, Any]:
    """Readiness probe. Returns HTTP 503 when the DB is unreachable so that
    load balancers / platform health checks treat the instance as unhealthy.
    """
    try:
        with get_cursor() as cur:
            cur.execute("SELECT 1;")
            cur.fetchone()
        return {"status": "ok"}
    except Exception as exc:  # noqa: BLE001
        response.status_code = 503
        return {"status": "error", "message": str(exc)}


@app.get("/news")
@limiter.limit("60/minute")
def get_news(request: Request, limit: int = Query(150, ge=1, le=500)) -> list[dict[str, Any]]:
    with get_cursor(dict_rows=True) as cur:
        cur.execute(
            f"SELECT {_SELECT} FROM news "
            "ORDER BY published DESC NULLS LAST, id DESC LIMIT %s;",
            (limit * 5,),
        )
        rows = cur.fetchall()
    return _allowed_articles(rows, limit)


@app.get("/news/{category}")
@limiter.limit("60/minute")
def get_news_by_category(
    request: Request,
    category: str,
    limit: int = Query(50, ge=1, le=300),
) -> list[dict[str, Any]]:
    category = category.lower().strip()
    if category not in VALID_CATEGORIES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid category. Use one of: {', '.join(sorted(VALID_CATEGORIES))}",
        )

    with get_cursor(dict_rows=True) as cur:
        cur.execute(
            f"SELECT {_SELECT} FROM news "
            "WHERE LOWER(category) = %s "
            "ORDER BY published DESC NULLS LAST, id DESC LIMIT %s;",
            (category, limit * 5),
        )
        rows = cur.fetchall()
    return _allowed_articles(rows, limit)


# One scrape at a time per process. run_scraper() mutates module-level provider
# state in scraper.py (_ACTIVE_PROVIDER_IDX, ai_client, AI_MODEL), and FastAPI
# runs sync endpoints in a threadpool, so two overlapping POSTs would race each
# other through the fallback chain.
_scrape_lock = threading.Lock()


@app.post("/scrape")
# Rejected attempts count against this too, which is the point: it caps token
# guessing. Kept above 1/min so a legitimate operator who fat-fingers the token
# isn't locked out of their own endpoint for a minute.
@limiter.limit("5/minute")
def trigger_scrape(request: Request) -> dict[str, Any]:
    expected = os.getenv("SCRAPE_API_TOKEN", "")

    # An unset token must CLOSE this door, not open it. The previous check was
    # `if expected and token != expected`, which skipped verification entirely
    # when the var was missing — and it is missing in every deploy config in
    # this repo. A scrape spends LLM credits and hits every publisher in
    # SOURCES, so an unauthenticated caller could bill and rate-limit us at will.
    if not expected:
        logger.error(
            "POST /scrape refused: SCRAPE_API_TOKEN is not set, so the endpoint "
            "cannot authenticate callers."
        )
        raise HTTPException(
            status_code=503,
            detail="Scrape endpoint disabled: SCRAPE_API_TOKEN is not configured.",
        )

    token = request.headers.get("authorization", "").removeprefix("Bearer ").strip()
    # Compare as bytes: secrets.compare_digest() raises TypeError on str inputs
    # that aren't ASCII-only, which would turn a non-ASCII token into a 500.
    if not secrets.compare_digest(token.encode("utf-8"), expected.encode("utf-8")):
        raise HTTPException(status_code=403, detail="Forbidden")

    if not _scrape_lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="A scrape is already running")

    try:
        from scraper import run_scraper

        run_scraper()
        return {"status": "ok", "message": "Scrape completed"}
    except Exception as exc:  # noqa: BLE001
        logger.exception("Manual scrape failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        _scrape_lock.release()


@app.get("/search")
@limiter.limit("30/minute")
def search_news(
    request: Request,
    q: str = Query(..., min_length=1, max_length=200),
    limit: int = Query(50, ge=1, le=200),
) -> list[dict[str, Any]]:
    like_q = f"%{q.strip()}%"
    with get_cursor(dict_rows=True) as cur:
        cur.execute(
            f"SELECT {_SELECT} FROM news "
            "WHERE title ILIKE %s "
            "   OR summary ILIKE %s "
            "   OR ai_summary ILIKE %s "
            "   OR source ILIKE %s "
            "ORDER BY published DESC NULLS LAST, id DESC LIMIT %s;",
            (like_q, like_q, like_q, like_q, limit * 5),
        )
        rows = cur.fetchall()
    return _allowed_articles(rows, limit)
