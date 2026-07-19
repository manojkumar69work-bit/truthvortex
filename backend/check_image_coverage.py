#!/usr/bin/env python3
"""
Image-coverage checker for TruthVortex sources.

The scraper always falls back to the TruthVortex placeholder, so you cannot tell
from the code which feeds actually ship real images. This script fetches every
source LIVE (needs internet) and reports, per channel, how many sampled
articles carry a genuine image (non-empty, not a logo, not the placeholder).

Usage:
    python check_image_coverage.py                # report only
    python check_image_coverage.py --remove       # also delete 0-image channels
    python check_image_coverage.py --remove --min-coverage 0.25
                                                  # delete channels under 25%

--remove edits scraper.py IN PLACE (a .bak backup is written first).
"""
import argparse
import os
import re
import shutil
import sys

# Defensive: avoid any module-level failures (AI/DB are not used here).
os.environ.setdefault("NVIDIA_API_KEY", "dummy-key-for-coverage-check")
os.environ.setdefault("SAFE_IMAGES_ONLY", "false")  # we read raw source images

HERE = os.path.dirname(os.path.abspath(__file__))
SCRAPER_PATH = os.path.join(HERE, "scraper.py")
sys.path.insert(0, HERE)

try:
    import scraper  # noqa: E402
except Exception as e:  # pragma: no cover
    print("ERROR: could not import scraper.py:", repr(e))
    print("Run this from the backend/ folder with the venv activated.")
    sys.exit(1)


def has_real_image(url: str) -> bool:
    if not url:
        return False
    if url == getattr(scraper, "FALLBACK_NS_IMAGE", "__none__"):
        return False
    try:
        if scraper.is_probably_logo_image(url):
            return False
    except Exception:
        pass
    return True


def coverage_for(source: dict):
    """Return (total_articles, articles_with_real_image)."""
    stype = source.get("type", "rss")
    try:
        if stype == "page":
            articles = scraper.scrape_page_source(source)
        else:
            articles = scraper.scrape_rss_source(source)
    except Exception as e:
        print(f"    ! fetch failed for {source['name']}: {e!r}")
        return 0, 0
    total = len(articles)
    with_img = sum(1 for a in articles if has_real_image(a.get("image", "")))
    return total, with_img


def remove_sources_from_scraper(names_to_remove):
    """Delete the matching 6-line source dict blocks from scraper.py."""
    if not names_to_remove:
        return []
    shutil.copyfile(SCRAPER_PATH, SCRAPER_PATH + ".bak")
    lines = open(SCRAPER_PATH, encoding="utf-8").read().split("\n")
    remove = set()
    removed = []
    for i, line in enumerate(lines):
        m = re.match(r'\s*"name":\s*"([^"]+)",', line)
        if m and m.group(1) in names_to_remove:
            start, end = i - 1, i + 4  # {, name, url, category, type, },
            if lines[start].strip() == "{" and lines[end].strip() == "},":
                for j in range(start, end + 1):
                    remove.add(j)
                removed.append(m.group(1))
            else:
                print(f"    ! skipped {m.group(1)} (unexpected block shape)")
    new_lines = [l for k, l in enumerate(lines) if k not in remove]
    open(SCRAPER_PATH, "w", encoding="utf-8").write("\n".join(new_lines))
    return removed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--remove", action="store_true",
                    help="delete channels at/under the coverage threshold")
    ap.add_argument("--min-coverage", type=float, default=0.0,
                    help="fraction (0..1). Channels with coverage <= this are "
                         "removal candidates. Default 0.0 = only zero-image.")
    args = ap.parse_args()

    sources = scraper.SOURCES
    print(f"Checking {len(sources)} sources live...\n")
    rows = []
    for s in sources:
        total, with_img = coverage_for(s)
        cov = (with_img / total) if total else 0.0
        rows.append((s["name"], s.get("category", "?"), total, with_img, cov))

    rows.sort(key=lambda r: r[4])
    print(f"{'COVER':>6}  {'IMG/ALL':>9}  {'CATEGORY':<10}  CHANNEL")
    print("-" * 60)
    for name, cat, total, with_img, cov in rows:
        print(f"{cov*100:5.0f}%  {with_img:>4}/{total:<4}  {cat:<10}  {name}")

    candidates = [r[0] for r in rows if r[4] <= args.min_coverage]
    print("\nRemoval candidates (coverage <= "
          f"{args.min_coverage*100:.0f}%): {len(candidates)}")
    for c in candidates:
        print("   -", c)

    if args.remove and candidates:
        removed = remove_sources_from_scraper(set(candidates))
        print(f"\nRemoved {len(removed)} channels from scraper.py "
              f"(backup: scraper.py.bak):")
        for r in removed:
            print("   x", r)
    elif args.remove:
        print("\nNothing to remove.")
    else:
        print("\nReport only. Re-run with --remove to delete the candidates.")


if __name__ == "__main__":
    main()
