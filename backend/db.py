"""Database connection helpers.

Provides a module-level ``ThreadedConnectionPool`` (1-5 connections) that
both the API and the scraper share. All callers should use ``get_conn()``
as a context manager so connections are always returned to the pool.

If ``DATABASE_URL`` is set, it takes precedence. Otherwise the
``DB_*`` variables are used. Hardcoded usernames are intentionally NOT
used — fall back to the current OS user, or fail loudly.
"""

from __future__ import annotations

import os
import threading
from contextlib import contextmanager
from typing import Iterator

import psycopg2
import psycopg2.extensions
from psycopg2.extras import RealDictCursor
from psycopg2.pool import ThreadedConnectionPool

_POOL: ThreadedConnectionPool | None = None
_POOL_LOCK = threading.Lock()

# Fail fast rather than hang when the database host stops answering. A managed
# instance that is suspended or deleted blackholes the connection instead of
# refusing it, so without this psycopg2 waits indefinitely and every request —
# including /health, whose whole job is to report the outage — hangs with it.
_CONNECT_TIMEOUT = int(os.getenv("DB_CONNECT_TIMEOUT", "5"))

# Server-side guards so a runaway query doesn't pin a pool slot.
_STATEMENT_GUARDS = "-c statement_timeout=15000 -c lock_timeout=7000"


def _build_connect_kwargs() -> dict:
    """Return kwargs for ``psycopg2.connect`` from env."""
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        # psycopg2 hands the URL's own fields through as-is, but it applies no
        # timeouts of its own — and this is the branch every deployment takes.
        # Add them here or production runs with none. Anything already spelled
        # out in DATABASE_URL wins: kwargs override the DSN in make_dsn(), so
        # only supply what the URL didn't.
        kwargs: dict = {"dsn": database_url}
        if "connect_timeout" not in database_url:
            kwargs["connect_timeout"] = _CONNECT_TIMEOUT
        if "options" not in database_url:
            kwargs["options"] = _STATEMENT_GUARDS
        return kwargs

    user = os.getenv("DB_USER") or os.getenv("USER") or os.getenv("USERNAME")
    if not user:
        raise RuntimeError(
            "Database credentials missing: set DATABASE_URL or DB_USER."
        )

    return {
        "dbname": os.getenv("DB_NAME", "newsdb"),
        "user": user,
        "password": os.getenv("DB_PASSWORD"),
        "host": os.getenv("DB_HOST", "localhost"),
        "port": os.getenv("DB_PORT", "5432"),
        "connect_timeout": _CONNECT_TIMEOUT,
        "options": _STATEMENT_GUARDS,
    }


def _get_pool() -> ThreadedConnectionPool:
    global _POOL
    if _POOL is None:
        with _POOL_LOCK:
            if _POOL is None:
                kwargs = _build_connect_kwargs()
                _POOL = ThreadedConnectionPool(
                    minconn=1,
                    maxconn=int(os.getenv("DB_POOL_MAX", "5")),
                    **kwargs,
                )
    return _POOL


@contextmanager
def get_conn() -> Iterator[psycopg2.extensions.connection]:
    """Borrow a pooled connection; return it on exit."""
    pool = _get_pool()
    conn = pool.getconn()
    try:
        # Validate connection is alive before yielding.
        # Use a loop with max retries to avoid leaking connections if validation fails repeatedly.
        for _ in range(3):
            if conn.closed != 0:
                pool.putconn(conn)
                conn = pool.getconn()
                continue
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1;")
                break
            except Exception:
                pool.putconn(conn)
                conn = pool.getconn()
        else:
            # All retries exhausted; raise the last error
            raise RuntimeError("Failed to obtain a valid database connection after 3 attempts")
        yield conn
    finally:
        # Roll back any uncommitted transaction before returning to the pool.
        try:
            if conn.closed == 0 and conn.status != psycopg2.extensions.STATUS_READY:
                conn.rollback()
        except Exception:
            pass
        # A borrower may have set autocommit=True (e.g. ensure_schema's DDL).
        # Reset it so the next borrower of this pooled connection gets normal
        # transactional behavior and its rollback-on-error still works.
        try:
            if conn.closed == 0 and conn.autocommit:
                conn.autocommit = False
        except Exception:
            pass
        pool.putconn(conn)


@contextmanager
def get_cursor(
    commit: bool = False,
    dict_rows: bool = False,
) -> Iterator[psycopg2.extensions.cursor]:
    """Convenience: get a cursor; optionally commit on success.

    ``dict_rows=True`` returns rows as ``dict`` (column → value).
    """
    with get_conn() as conn:
        factory = RealDictCursor if dict_rows else None
        cur = conn.cursor(cursor_factory=factory)
        try:
            yield cur
            if commit:
                conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()


def close_pool() -> None:
    """Tear down the pool (used in tests / shutdown)."""
    global _POOL
    with _POOL_LOCK:
        if _POOL is not None:
            _POOL.closeall()
            _POOL = None
