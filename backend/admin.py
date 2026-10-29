"""Newsroom admin API: write, upload, manage and search articles.

Every /admin route requires the ADMIN_TOKEN bearer token (see security.py) and
every change is written to the ``admin_audit`` table.

Content rule enforced here, not just written in the policy page: an article
written in the newsroom is published as a Red4ce original, so its image must be
one uploaded to our own media store, and the author must confirm the text and
photo are ours. External image URLs are refused for originals.
"""

# No `from __future__ import annotations` here: slowapi's decorator wraps each
# route, and FastAPI then resolves string annotations against slowapi's module,
# where ArticleIn doesn't exist — the body model silently became a query param.
import logging
import os
import re
from datetime import timezone
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field, field_validator

from analytics import summary as analytics_summary
from categories import VALID_CATEGORIES
from db import get_cursor
from security import limiter, require_admin

logger = logging.getLogger("red4ce.admin")

SITE_NAME = os.getenv("SITE_NAME", "Red4ce")

admin_router = APIRouter(prefix="/admin", dependencies=[Depends(require_admin)])
media_router = APIRouter()

_MEDIA_PATH_RE = re.compile(r"^/media/\d{1,10}$")
_MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", str(3 * 1024 * 1024)))

# Magic bytes → content type. The client's Content-Type header is never trusted:
# whatever we store is served back with the type sniffed here.
_SIGNATURES: tuple[tuple[bytes, str], ...] = (
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"GIF87a", "image/gif"),
    (b"GIF89a", "image/gif"),
)


def _sniff_image(data: bytes) -> str | None:
    for signature, content_type in _SIGNATURES:
        if data.startswith(signature):
            return content_type
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def _audit(ip: str, action: str, article_id: int | None = None, detail: str = "") -> None:
    try:
        with get_cursor(commit=True) as cur:
            cur.execute(
                "INSERT INTO admin_audit (action, article_id, detail, ip) VALUES (%s, %s, %s, %s);",
                (action, article_id, detail[:500], ip),
            )
    except Exception as exc:  # noqa: BLE001
        # The change already happened; losing its audit row must not 500 the request.
        logger.error("audit write failed (%s %s): %s", action, article_id, exc)
    logger.info("admin %s article=%s ip=%s %s", action, article_id, ip, detail)


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


# ─── Models ────────────────────────────────────────────────────
def _strip_text(value: str | None) -> str | None:
    return value.strip() if isinstance(value, str) else value


def _clean_category(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.lower().strip()
    if value not in VALID_CATEGORIES:
        raise ValueError(f"category must be one of {sorted(VALID_CATEGORIES)}")
    return value


def _clean_image(value: str | None) -> str | None:
    """Only images from our own media store; "" (clear) passes through."""
    if not value:
        return value
    if not _MEDIA_PATH_RE.match(value):
        raise ValueError("image must be uploaded through /admin/media (external URLs are not allowed)")
    return value


class ArticleIn(BaseModel):
    title: str = Field(min_length=3, max_length=300)
    # 40 is the frontend's floor for a displayable summary (hasValidAiSummary).
    body: str = Field(min_length=40, max_length=20000)
    summary: str | None = Field(default=None, max_length=600)
    category: str
    image: str | None = Field(default=None, max_length=40)
    author: str | None = Field(default=None, max_length=80)
    status: Literal["published", "draft"] = "published"
    originality_confirmed: bool = False

    _strip = field_validator("title", "body", "summary", "author")(_strip_text)
    _category = field_validator("category")(_clean_category)
    _image = field_validator("image")(_clean_image)


class ArticlePatch(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=300)
    body: str | None = Field(default=None, min_length=40, max_length=20000)
    summary: str | None = Field(default=None, max_length=600)
    category: str | None = None
    image: str | None = Field(default=None, max_length=40)
    author: str | None = Field(default=None, max_length=80)
    status: Literal["published", "draft"] | None = None

    _strip = field_validator("title", "body", "summary", "author")(_strip_text)
    _category = field_validator("category")(_clean_category)
    _image = field_validator("image")(_clean_image)


_ADMIN_SELECT = (
    "id, source, title, title_original, link, summary, ai_summary, image, published, "
    "category, is_original, status, author, updated_at"
)


def _admin_row(row: dict[str, Any]) -> dict[str, Any]:
    out = dict(row)
    for key in ("published", "updated_at"):
        value = out.get(key)
        if value is not None:
            if value.tzinfo is None:
                value = value.replace(tzinfo=timezone.utc)
            out[key] = value.isoformat()
    return out


def _fetch_article(article_id: int) -> dict[str, Any]:
    with get_cursor(dict_rows=True) as cur:
        cur.execute(f"SELECT {_ADMIN_SELECT} FROM news WHERE id = %s;", (article_id,))
        row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Article not found")
    return _admin_row(row)


def _excerpt(body: str, limit: int = 300) -> str:
    flat = " ".join(body.split())
    return flat if len(flat) <= limit else flat[: limit - 1].rstrip() + "…"


# ─── Routes ────────────────────────────────────────────────────
@admin_router.get("/me")
@limiter.limit("30/minute")
def me(request: Request) -> dict[str, Any]:
    """Token check for the login screen."""
    return {"ok": True, "site": SITE_NAME}


@admin_router.get("/articles")
@limiter.limit("60/minute")
def list_articles(
    request: Request,
    q: str = Query("", max_length=200),
    category: str = Query("", max_length=20),
    origin: Literal["all", "original", "feed"] = "all",
    status: Literal["all", "published", "draft"] = "all",
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0, le=100000),
) -> dict[str, Any]:
    where: list[str] = []
    params: list[Any] = []

    term = q.strip()
    if term:
        if term.isdigit() and len(term) <= 9:
            where.append("(id = %s OR title ILIKE %s)")
            params += [int(term), f"%{_escape_like(term)}%"]
        else:
            like = f"%{_escape_like(term)}%"
            where.append(
                "(title ILIKE %s OR title_original ILIKE %s OR ai_summary ILIKE %s "
                "OR summary ILIKE %s OR source ILIKE %s OR author ILIKE %s)"
            )
            params += [like] * 6
    if category:
        if category not in VALID_CATEGORIES:
            raise HTTPException(status_code=400, detail="Invalid category")
        where.append("LOWER(category) = %s")
        params.append(category)
    if origin != "all":
        where.append("is_original = %s")
        params.append(origin == "original")
    if status != "all":
        where.append("status = %s")
        params.append(status)

    clause = f"WHERE {' AND '.join(where)} " if where else ""
    with get_cursor(dict_rows=True) as cur:
        cur.execute(f"SELECT COUNT(*) AS n FROM news {clause};", params)
        total = cur.fetchone()["n"]
        cur.execute(
            f"SELECT {_ADMIN_SELECT} FROM news {clause}"
            "ORDER BY published DESC NULLS LAST, id DESC LIMIT %s OFFSET %s;",
            [*params, limit, offset],
        )
        rows = cur.fetchall()
    return {"total": total, "items": [_admin_row(r) for r in rows]}


@admin_router.get("/articles/{article_id}")
@limiter.limit("60/minute")
def get_article(request: Request, article_id: int) -> dict[str, Any]:
    return _fetch_article(article_id)


@admin_router.post("/articles", status_code=201)
@limiter.limit("20/minute")
def create_article(
    request: Request, article: ArticleIn, ip: str = Depends(require_admin)
) -> dict[str, Any]:
    if not article.originality_confirmed:
        raise HTTPException(
            status_code=422,
            detail="Confirm the text and image are original to Red4ce before publishing.",
        )
    with get_cursor(commit=True, dict_rows=True) as cur:
        cur.execute(
            "INSERT INTO news (source, title, title_original, link, summary, ai_summary, image, "
            "  published, category, is_original, status, author, updated_at) "
            "VALUES (%s, %s, %s, NULL, %s, %s, %s, NOW() AT TIME ZONE 'UTC', %s, TRUE, %s, %s, "
            "  NOW() AT TIME ZONE 'UTC') "
            "RETURNING id;",
            (
                SITE_NAME,
                article.title,
                article.title,
                article.summary or _excerpt(article.body),
                article.body,
                article.image or "",
                article.category,
                article.status,
                article.author or None,
            ),
        )
        new_id = cur.fetchone()["id"]
    _audit(ip, "create", new_id, f"{article.status} · {article.title[:120]}")
    return _fetch_article(new_id)


@admin_router.put("/articles/{article_id}")
@limiter.limit("30/minute")
def update_article(
    request: Request,
    article_id: int,
    patch: ArticlePatch,
    ip: str = Depends(require_admin),
) -> dict[str, Any]:
    current = _fetch_article(article_id)
    changes = patch.model_dump(exclude_unset=True)
    if not changes:
        return current

    columns: dict[str, Any] = {}
    if "title" in changes and changes["title"]:
        columns["title"] = changes["title"]
        if current["is_original"]:
            columns["title_original"] = changes["title"]
    if "body" in changes and changes["body"]:
        columns["ai_summary"] = changes["body"]
        if current["is_original"] and "summary" not in changes:
            columns["summary"] = _excerpt(changes["body"])
    if "summary" in changes:
        columns["summary"] = changes["summary"] or ""
    for key in ("category", "status"):
        if changes.get(key):
            columns[key] = changes[key]
    if "image" in changes:
        columns["image"] = changes["image"] or ""
    if "author" in changes:
        columns["author"] = changes["author"] or None

    if not columns:
        return current

    assignments = ", ".join(f"{col} = %s" for col in columns)
    with get_cursor(commit=True) as cur:
        cur.execute(
            f"UPDATE news SET {assignments}, updated_at = NOW() AT TIME ZONE 'UTC' WHERE id = %s;",
            [*columns.values(), article_id],
        )
    _audit(ip, "update", article_id, ", ".join(sorted(columns)))
    return _fetch_article(article_id)


@admin_router.delete("/articles/{article_id}", status_code=204)
@limiter.limit("30/minute")
def delete_article(
    request: Request, article_id: int, ip: str = Depends(require_admin)
) -> Response:
    current = _fetch_article(article_id)
    with get_cursor(commit=True) as cur:
        cur.execute("DELETE FROM news WHERE id = %s;", (article_id,))
    _audit(ip, "delete", article_id, f"{current['source']} · {(current['title'] or '')[:120]}")
    return Response(status_code=204)


@admin_router.post("/media", status_code=201)
@limiter.limit("20/minute")
async def upload_media(request: Request, ip: str = Depends(require_admin)) -> dict[str, Any]:
    """Upload one image as the raw request body (no multipart parser needed)."""
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > _MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Image is larger than the upload limit.")

    data = bytearray()
    async for chunk in request.stream():
        data.extend(chunk)
        if len(data) > _MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="Image is larger than the upload limit.")
    if not data:
        raise HTTPException(status_code=400, detail="Empty upload.")

    content_type = _sniff_image(bytes(data))
    if content_type is None:
        raise HTTPException(status_code=415, detail="Only JPEG, PNG, WebP or GIF images are accepted.")

    with get_cursor(commit=True, dict_rows=True) as cur:
        cur.execute(
            "INSERT INTO media (content_type, data, size) VALUES (%s, %s, %s) RETURNING id;",
            (content_type, bytes(data), len(data)),
        )
        media_id = cur.fetchone()["id"]
    _audit(ip, "upload", None, f"media {media_id} · {content_type} · {len(data)} bytes")
    return {"id": media_id, "url": f"/media/{media_id}", "content_type": content_type}


@admin_router.get("/analytics")
@limiter.limit("30/minute")
def get_analytics(request: Request, days: int = Query(7, ge=1, le=90)) -> dict[str, Any]:
    return analytics_summary(days)


@admin_router.get("/audit")
@limiter.limit("30/minute")
def get_audit(request: Request, limit: int = Query(50, ge=1, le=200)) -> list[dict[str, Any]]:
    with get_cursor(dict_rows=True) as cur:
        cur.execute(
            "SELECT id, ts, action, article_id, detail, ip FROM admin_audit "
            "ORDER BY id DESC LIMIT %s;",
            (limit,),
        )
        rows = cur.fetchall()
    for row in rows:
        row["ts"] = row["ts"].replace(tzinfo=timezone.utc).isoformat()
    return rows


# ─── Public media ──────────────────────────────────────────────
@media_router.get("/media/{media_id}")
@limiter.limit("300/minute")
def get_media(request: Request, media_id: int) -> Response:
    with get_cursor() as cur:
        cur.execute("SELECT content_type, data FROM media WHERE id = %s;", (media_id,))
        row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Not found")
    content_type, data = row
    return Response(
        content=bytes(data),
        media_type=content_type,
        headers={
            # Media rows are never edited in place, so the URL is immutable.
            "Cache-Control": "public, max-age=31536000, immutable",
            "Content-Security-Policy": "default-src 'none'; sandbox",
            # The frontend lives on another origin and embeds these images.
            "Cross-Origin-Resource-Policy": "cross-origin",
        },
    )
