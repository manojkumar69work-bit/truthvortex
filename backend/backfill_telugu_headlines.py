"""Backfill the displayed `title` column with an AI-generated Telugu headline
for every row whose current `title` is not in Telugu script.

Reuses scraper.generate_ai_headline() and scraper.has_telugu_script() so the
prompt stays in sync with what new scrapes will produce.

Run from the backend/ directory:

    cd backend
    ../venv/bin/python backfill_telugu_headlines.py            # dry run
    ../venv/bin/python backfill_telugu_headlines.py --apply    # write to DB
"""
from __future__ import annotations

import argparse
import os
import sys

# Ensure backend/ is on the path so `import scraper` resolves.
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

import psycopg2  # noqa: E402

import scraper  # noqa: E402
from scraper import has_telugu_script, generate_ai_headline  # noqa: E402


def connect() -> psycopg2.extensions.connection:
    # scraper.py loads backend/.env via load_dotenv() at import time, which
    # also sets DATABASE_URL into os.environ.
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise SystemExit("DATABASE_URL not set in backend/.env")
    return psycopg2.connect(db_url)


def find_non_telugu_titles(conn) -> list[tuple[int, str, str | None, str | None]]:
    """Return (id, title, title_original, ai_summary) for rows whose
    displayed title is not in Telugu script.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, title, title_original, ai_summary
            FROM news
            WHERE title IS NOT NULL
              AND title <> ''
            ORDER BY published DESC NULLS LAST, id DESC;
            """
        )
        rows = cur.fetchall()
    return [
        r
        for r in rows
        if not has_telugu_script(r[1] or "", min_chars=2)
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually write the AI-translated headline to the DB.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Only process the first N rows (0 = all).",
    )
    args = parser.parse_args()

    if not scraper.ai_client:
        print(
            "ERROR: scraper.ai_client is None — check GROQ_API_KEY "
            "(or AI_API_KEY / NVIDIA_API_KEY) in backend/.env.",
            file=sys.stderr,
        )
        return 2

    conn = connect()
    try:
        rows = find_non_telugu_titles(conn)
        if args.limit:
            rows = rows[: args.limit]

        print(f"Found {len(rows)} row(s) whose title is not in Telugu script.")
        if not args.apply:
            print("Dry run. Re-run with --apply to write changes.")

        for row_id, title, title_original, ai_summary in rows:
            src = title_original or title
            print(f"\n[id={row_id}] src='{(src or '')[:80]}'")
            try:
                new_title = generate_ai_headline(
                    src or "",
                    ai_summary or "",
                    category="breaking",
                )
            except Exception as exc:  # noqa: BLE001
                print(f"  ERROR: {exc}")
                continue

            if not new_title:
                print("  → AI returned empty headline; skipping.")
                continue

            if not has_telugu_script(new_title, min_chars=2):
                print(f"  → AI returned non-Telugu headline: {new_title!r}")
                continue

            print(f"  → new Telugu title: {new_title}")
            if args.apply:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE news SET title = %s WHERE id = %s;",
                        (new_title, row_id),
                    )
                conn.commit()
                print("  ✓ wrote to DB.")
            else:
                print("  (dry run, not written)")

            # Pace requests to stay under Groq free-tier rate limits.
            import time
            time.sleep(2.0)

        print("\nDone.")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
