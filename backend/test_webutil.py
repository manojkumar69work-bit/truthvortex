#!/usr/bin/env python3
"""Unit tests for webutil's image-vetting and text-repair helpers.

Deliberately dependency-free (plain asserts, no pytest) so CI can run it with
nothing but beautifulsoup4 installed — the same reasoning as check_feeds.py.

Usage:
    cd backend && python test_webutil.py
"""
from __future__ import annotations

import sys

import webutil as w

failures: list[str] = []


def check(label: str, actual, expected) -> None:
    if actual == expected:
        print(f"  ok   {label}")
    else:
        print(f"  FAIL {label}\n         expected: {expected!r}\n         actual:   {actual!r}")
        failures.append(label)


print("srcset parsing")
# Commas inside CDN transform paths are the reason srcset is tokenized on
# whitespace rather than split on commas.
check(
    "picks largest w, comma-bearing CDN paths intact",
    w.pick_srcset_largest(
        "https://cdn/i/w_640,h_360/a.jpg 640w, https://cdn/i/w_1600,h_900/b.jpg 1600w"
    ),
    "https://cdn/i/w_1600,h_900/b.jpg",
)
check(
    "falls back to largest x when no w descriptors",
    w.pick_srcset_largest("https://cdn/a.jpg 1x, https://cdn/b.jpg 3x"),
    "https://cdn/b.jpg",
)
check(
    "single bare URL, no descriptor",
    w.pick_srcset_largest("https://cdn/only.jpg"),
    "https://cdn/only.jpg",
)
check("empty srcset", w.pick_srcset_largest(""), "")
check("max width read off descriptors", w.srcset_max_width("a.jpg 640w, b.jpg 1600w"), 1600)
check("max width with no w descriptors", w.srcset_max_width("a.jpg 2x"), 0)

print("dimension gate")
# The core invariant: absent/unparseable dimensions must never read as small,
# or every image without width/height attributes gets discarded.
check("unknown dimensions are not tiny", w.is_tiny_image(None, None), False)
check("empty strings are not tiny", w.is_tiny_image("", ""), False)
check("percentages are not tiny", w.is_tiny_image("100%", "100%"), False)
check("keyword 'auto' is not tiny", w.is_tiny_image("auto", None), False)
check("zero is unknown, not tiny", w.is_tiny_image(0, 0), False)
check("100x100 is tiny", w.is_tiny_image("100", "100"), True)
check("px suffix parses", w.is_tiny_image("1192px", None), False)
check("narrow width alone is tiny", w.is_tiny_image("120", None), True)
check("short height alone is tiny", w.is_tiny_image(None, "80"), True)
check("large photo is not tiny", w.is_tiny_image("1200", "700"), False)

print("logo / junk filter")
check("logo filename rejected", w.clean_image_url("https://cdn/a/logo-main.png"), "")
check("svg rejected", w.clean_image_url("https://cdn/a/hero.svg"), "")
# Directory-scoped false positive this filter was specifically fixed for.
check(
    "'icon' in a DIRECTORY does not reject the photo",
    w.clean_image_url("https://cdn/icon/real-photo.jpg"),
    "https://cdn/icon/real-photo.jpg",
)
check(
    "'default' in a directory does not reject the photo",
    w.clean_image_url("https://cdn/default/news-photo.jpg"),
    "https://cdn/default/news-photo.jpg",
)

print("tracking pixels and beacons")
check(
    "inline 1x1 gif data URI",
    w.is_data_or_tiny_uri("data:image/gif;base64,R0lGODlh"),
    True,
)
check("real URL is not a data URI", w.is_data_or_tiny_uri("https://cdn/a.jpg"), False)
# Regression: observed live on Deccan Chronicle's homepage, which offers a
# Comscore beacon as its first <img> when the page has no og:image.
check(
    "comscore beacon rejected (subdomain)",
    w.clean_image_url("https://sb.scorecardresearch.com/p?c1=2&c2=39080398"),
    "",
)
check(
    "beacon host matched on apex too",
    w.is_tracker_image("https://scorecardresearch.com/p?c1=2"),
    True,
)
check(
    "beacon host with port",
    w.is_tracker_image("https://sb.scorecardresearch.com:443/p"),
    True,
)
check(
    "publisher host that merely CONTAINS a tracker name is kept",
    w.is_tracker_image("https://cdn.notchartbeat.com/photo.jpg"),
    False,
)
check("normal photo is not a tracker", w.is_tracker_image("https://cdn/a.jpg"), False)

print("url normalization")
check(
    "protocol-relative gains the base scheme",
    w.normalize_url("//cdn/a.jpg", "https://site/x/y"),
    "https://cdn/a.jpg",
)
check(
    "relative path resolves against the base",
    w.normalize_url("../img/a.jpg", "https://site/x/y/page.html"),
    "https://site/x/img/a.jpg",
)
check("empty url stays empty", w.normalize_url("", "https://site"), "")

print("text repair")
# Build the mojibake the way it actually happens — utf-8 bytes read back as
# latin1 — rather than pasting a literal, which mangles the combining marks.
TELUGU = "తెలుగు"
MOJIBAKE = TELUGU.encode("utf-8").decode("latin1")
check("mojibake fixture really is mangled", MOJIBAKE == TELUGU, False)
check(
    "utf-8 Telugu mis-decoded as latin1 is repaired",
    w.fix_mojibake_text(MOJIBAKE),
    TELUGU,
)
check("clean Telugu is left alone", w.fix_mojibake_text("తెలుగు"), "తెలుగు")
check(
    "html entities and tags stripped",
    w.clean_html_text("<p>Hello &amp;   world</p>"),
    "Hello & world",
)
check("empty text", w.clean_html_text(""), "")

print()
if failures:
    print(f"FAIL: {len(failures)} check(s) failed: {failures}")
    sys.exit(1)
print("PASS: all webutil checks clean")
