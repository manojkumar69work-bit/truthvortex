#!/usr/bin/env python3
"""clear_db.py — wipe all rows from the `news` table.

DESTRUCTIVE and irreversible. Uses the same DB connection as the app
(DATABASE_URL, or the DB_* fallback vars), so it clears whatever database
your environment points at — run it where your real DATABASE_URL is set
(locally, or in a Render shell for production).

Safe by default: with no flag it only REPORTS the current row count.
To actually delete, pass --yes:

    # dry run (just shows the count):
    python clear_db.py

    # actually wipe everything and reset ids:
    python clear_db.py --yes
"""
from __future__ import annotations

import sys

from db import get_cursor


def main() -> int:
    confirm = "--yes" in sys.argv[1:]

    with get_cursor(commit=confirm) as cur:
        cur.execute("SELECT count(*) FROM news;")
        count = cur.fetchone()[0]
        print(f"news table currently has {count} row(s).")

        if not confirm:
            print("Dry run — nothing deleted. Re-run with --yes to wipe all rows.")
            return 0

        # TRUNCATE is faster than DELETE and RESTART IDENTITY resets the id
        # sequence so new articles start from 1 again.
        cur.execute("TRUNCATE TABLE news RESTART IDENTITY;")
        print(f"Deleted all {count} row(s). The `news` table is now empty.")
        print("The scraper will repopulate it on its next run.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
