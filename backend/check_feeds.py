#!/usr/bin/env python3
"""
check_feeds.py — Authoritative RSS feed liveness checker for TruthVortex.

Why this exists:
  Feed liveness can only be confirmed with a real HTTP request. This script
  fetches every feed in scraper.py's SOURCES list, parses it, and reports
  which feeds are alive (HTTP < 400 AND at least one entry parsed) per category.

  It reads SOURCES *statically* (via ast.literal_eval) so it does NOT import
  scraper.py and therefore needs no API keys / DB / env to run.

Run it anywhere with internet:
    cd backend
    pip install requests feedparser   # already in requirements.txt
    python check_feeds.py

Exit code is non-zero if any category has fewer than MIN_PER_CATEGORY live feeds,
so you can wire it into CI or a pre-deploy check.
"""
from __future__ import annotations

import ast
import concurrent.futures
import os
import sys
from collections import defaultdict

import feedparser
import requests

MIN_PER_CATEGORY = int(os.getenv("MIN_PER_CATEGORY", "3"))
TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "12"))
MAX_WORKERS = int(os.getenv("CHECK_WORKERS", "8"))
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
HERE = os.path.dirname(os.path.abspath(__file__))
SCRAPER_PATH = os.path.join(HERE, "scraper.py")


def load_sources() -> list[dict]:
    """Extract the SOURCES list literal from scraper.py without importing it."""
    with open(SCRAPER_PATH, "r", encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "SOURCES":
                    return ast.literal_eval(node.value)
    raise SystemExit("Could not find SOURCES in scraper.py")


def check_one(src: dict) -> dict:
    name = src.get("name", "?")
    url = src.get("url", "")
    category = src.get("category", "?")
    result = {"name": name, "url": url, "category": category,
              "ok": False, "status": None, "entries": 0, "error": ""}
    try:
        resp = requests.get(url, timeout=TIMEOUT,
                            headers={"User-Agent": USER_AGENT})
        result["status"] = resp.status_code
        parsed = feedparser.parse(resp.content)
        result["entries"] = len(parsed.entries)
        result["ok"] = resp.status_code < 400 and len(parsed.entries) > 0
        if not result["ok"] and not result["error"]:
            result["error"] = (
                f"HTTP {resp.status_code}, {len(parsed.entries)} entries"
            )
    except Exception as exc:  # noqa: BLE001
        result["error"] = f"{type(exc).__name__}: {exc}"
    return result


def main() -> int:
    sources = load_sources()
    print(f"Checking {len(sources)} feeds (timeout={TIMEOUT}s, "
          f"workers={MAX_WORKERS})...\n")

    results: list[dict] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        for res in pool.map(check_one, sources):
            results.append(res)

    by_cat: dict[str, list[dict]] = defaultdict(list)
    for r in results:
        by_cat[r["category"]].append(r)

    failing_categories = []
    for category in sorted(by_cat):
        rows = by_cat[category]
        live = [r for r in rows if r["ok"]]
        flag = "" if len(live) >= MIN_PER_CATEGORY else "  <-- BELOW MINIMUM"
        print(f"== {category.upper()} : {len(live)}/{len(rows)} live{flag}")
        for r in rows:
            mark = "OK " if r["ok"] else "XX "
            detail = f"{r['entries']} entries" if r["ok"] else r["error"]
            print(f"   {mark} {r['name']:<34} {detail}")
            if not r["ok"]:
                print(f"        {r['url']}")
        if len(live) < MIN_PER_CATEGORY:
            failing_categories.append(category)
        print()

    total_live = sum(1 for r in results if r["ok"])
    print(f"TOTAL: {total_live}/{len(results)} feeds live across "
          f"{len(by_cat)} categories.")
    if failing_categories:
        print("\nFAIL: these categories have fewer than "
              f"{MIN_PER_CATEGORY} live feeds: "
              f"{', '.join(failing_categories)}")
        return 1
    print("\nPASS: every category has at least "
          f"{MIN_PER_CATEGORY} live feeds.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
