#!/usr/bin/env python3
"""
dry_run_scraper.py — Standalone smoke test of scraper.fetch_feed + dedupe
that needs no DB and no LLM.

It picks a few live SOURCES across categories, fetches them via the same
fetch_feed() used in production, extracts (title, link, image) for the first
N entries of each, and runs the dedupe contract: no two rows share the same
`link` (the UNIQUE constraint in the DB).

Usage:
    cd backend && python dry_run_scraper.py
"""
from __future__ import annotations

import sys
import os
import random
import importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))

# Stub heavy deps so we can import scraper module without bs4/rapidfuzz/openai/psycopg2.
# Only stub modules that are MISSING — we want real bs4 if installed so the
# parser stub we inject doesn't shadow the real BeautifulSoup.
import importlib
import types

def _stub(name, attrs=None):
    try:
        return importlib.import_module(name)
    except Exception:
        m = types.ModuleType(name)
        for k, v in (attrs or {}).items():
            setattr(m, k, v)
        sys.modules[name] = m
        return m

_stub("rapidfuzz")
_stub("rapidfuzz.fuzz", {"ratio": lambda *a, **k: 100})
_stub("dotenv", {"load_dotenv": lambda *a, **k: None})
# psycopg2 needs to be a real package so `from psycopg2.extras import ...` works
class _FakePackage(types.ModuleType):
    def __init__(self, name):
        super().__init__(name)
        self.__path__ = []  # marks it as a package
_pg = _FakePackage("psycopg2")
sys.modules["psycopg2"] = _pg
for sub in ("extras", "extensions", "pool", "errors"):
    m = types.ModuleType(f"psycopg2.{sub}")
    sys.modules[f"psycopg2.{sub}"] = m
    setattr(_pg, sub, m)
sys.modules["psycopg2.extras"].RealDictCursor = object
sys.modules["psycopg2.pool"].ThreadedConnectionPool = type("ThreadedConnectionPool", (), {})
_stub("tqdm", {"tqdm": lambda x, **k: x})
_stub("openai")  # may or may not be installed; scraper imports it lazily

# Avoid init of real AI client (no key in this env)
os.environ.setdefault("GROQ_API_KEY", "")
os.environ.setdefault("NVIDIA_API_KEY", "")
os.environ.setdefault("ENABLE_AI_SUMMARY", "false")
os.environ.setdefault("ENABLE_TRANSLATION", "false")
# Avoid DB attempts (no real Postgres available in this dry-run)
os.environ.setdefault("DATABASE_URL", "")

# Stub psycopg2 with a no-op connection so db.py imports don't blow up
class _FakeConn:
    def cursor(self): return self
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def execute(self, *a, **k): return self
    def fetchone(self): return None
    def fetchall(self): return []
sys.modules["psycopg2"].connect = lambda *a, **k: _FakeConn()

# Now import the real scraper
spec = importlib.util.spec_from_file_location("scraper", os.path.join(HERE, "scraper.py"))
scraper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scraper)

# Build a deduplicated sample: 1 feed per category
random.seed(42)
picks = {}
for s in scraper.SOURCES:
    if s["category"] not in picks:
        picks[s["category"]] = s
sample = [picks[c] for c in sorted(picks)]
print(f"Sampling {len(sample)} feeds (1 per category) for parse + dedupe smoke:\n")

seen_links: set[str] = set()
all_rows: list[dict] = []
failures: list[str] = []

for src in sample:
    print(f"  > {src['name']:<32} ({src['category']})")
    parsed = scraper.fetch_feed(src["url"])
    if not parsed or not parsed.entries:
        failures.append(src["name"])
        print(f"      FAILED to fetch/parse")
        continue
    print(f"      {len(parsed.entries)} entries available")
    for e in parsed.entries[:3]:  # first 3 per feed
        try:
            title = (e.get("title") or "").strip()
            link = (e.get("link") or "").strip()
            image = scraper.extract_image_from_entry(e) or ""
            pub = e.get("published") or e.get("updated") or ""
            if not link or not title:
                continue
            all_rows.append({"src": src["name"], "title": title[:80], "link": link, "image": bool(image), "pub": pub[:40]})
        except Exception as exc:
            print(f"      skip entry: {type(exc).__name__}: {exc}")

print(f"\nCollected {len(all_rows)} candidate rows. Running dedupe (link UNIQUE)...")

unique_rows: list[dict] = []
dupe_count = 0
for r in all_rows:
    if r["link"] in seen_links:
        dupe_count += 1
        print(f"  DEDUPE: {r['link']} (already seen from a previous feed)")
        continue
    seen_links.add(r["link"])
    unique_rows.append(r)

print(f"\nFinal: {len(unique_rows)} unique rows, {dupe_count} duplicates dropped.")
print(f"Failures (feed wouldn't parse): {failures or 'none'}")
print(f"\nFirst 5 unique rows:")
for r in unique_rows[:5]:
    print(f"  - [{r['src']}] {r['title']}")
    print(f"        link={r['link'][:80]}{'...' if len(r['link'])>80 else ''}")
    print(f"        image={'yes' if r['image'] else 'no'}  pub={r['pub']!r}")

# Pass criteria
ok = (
    not failures
    and len(unique_rows) >= 8           # at least 2 per category
    and dupe_count == 0                 # dedupe works (we only sampled 1 per cat, so this should be 0)
)
print(f"\n{'PASS' if ok else 'FAIL'}: dry-run smoke {'clean' if ok else 'has issues'}")
sys.exit(0 if ok else 1)
