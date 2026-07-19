"""One-time data migration to fix stored categories after the
``lifestyle`` → ``breaking`` rebucketing.

Run with::

    DATABASE_URL=... python -m backend.migrate_rebucket_legacy

Safe to re-run: it only updates rows that are not already in a
known category.
"""

from __future__ import annotations

import os
import sys

from categories import VALID_CATEGORIES, from_source, resolve

# Allow `python backend/migrate_rebucket_legacy.py`
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db import get_cursor  # noqa: E402


def main() -> int:
    with get_cursor(dict_rows=True) as cur:
        cur.execute("SELECT id, source, category FROM news;")
        rows = cur.fetchall()

    updates: list[tuple[str, int]] = []
    skipped = 0
    for row in rows:
        db_id, source, stored = row["id"], row["source"], row["category"]
        new_cat = resolve(stored=stored, source=source)
        if stored and stored.lower() in VALID_CATEGORIES:
            skipped += 1
            continue
        updates.append((new_cat, db_id))

    if not updates:
        print(f"No rows need re-bucketing. ({skipped} already valid.)")
        return 0

    print(f"Re-bucketing {len(updates)} rows, {skipped} already valid.")

    with get_cursor(commit=True) as cur:
        cur.executemany(
            "UPDATE news SET category = %s WHERE id = %s;",
            updates,
        )

    # Show the new distribution
    with get_cursor(dict_rows=True) as cur:
        cur.execute("SELECT category, COUNT(*) FROM news GROUP BY category ORDER BY 2 DESC;")
        for r in cur.fetchall():
            print(f"  {r['category']:>10s} : {r['count']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
