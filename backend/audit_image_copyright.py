#!/usr/bin/env python3
"""
One-shot image-copyright audit for every channel in scraper.py.

For each channel:
  1. Fetch the RSS feed.
  2. For every entry, take its RSS-level image (media_content / media_thumbnail /
     enclosures / inline <img>).
  3. If no RSS image, fetch the article HTML and grab og:image / twitter:image /
     first <img>.
  4. Run the channel's image URLs through the same `is_probably_logo_image`
     heuristic the scraper uses, plus a domain-level publisher-stamp check
     (e.g. images hosted on the publisher's own CDN that we know watermark).
  5. Bucket the channel: CLEAN / RISKY / DEAD / NO_IMAGES.

Output: a single human-readable report. No source code is modified.

Usage:
  .venv/bin/python audit_image_copyright.py
"""
from __future__ import annotations

import os
import re
import sys
import json
from urllib.parse import urlparse

import requests
import feedparser
from bs4 import BeautifulSoup

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import scraper  # noqa: E402

# Re-run the SOURCES list as defined in scraper.py (post has_image_risk).
ALL_SOURCES_RAW = [
    {"name": n, "url": u, "category": c, "type": t}
    for (n, u, c, t) in [
        # --- existing (post-prior-audit) ---
        ("UN News", "https://news.un.org/feed/subscribe/en/news/all/rss.xml", "breaking", "rss"),
        ("DW News English", "https://rss.dw.com/rdf/rss-en-all", "breaking", "rss"),
        ("Al Jazeera English", "https://www.aljazeera.com/xml/rss/all.xml", "breaking", "rss"),
        ("Visala Andhra", "https://visalaandhra.com/feed", "breaking", "rss"),
        ("Euronews - World", "https://www.euronews.com/rss?level=theme&name=news", "breaking", "rss"),
        ("The Hindu - National", "https://www.thehindu.com/news/national/?service=rss", "breaking", "rss"),
        ("Telangana Today", "https://telanganatoday.com/feed", "breaking", "rss"),
        ("DW Sports", "https://rss.dw.com/rdf/rss-en-sports", "sports", "rss"),
        ("Sportstar - The Hindu", "https://sportstar.thehindu.com/feeder/default.rss", "sports", "rss"),
        ("The Bridge", "https://thebridge.in/feed/", "sports", "rss"),
        ("ESPNcricinfo - India Team", "https://www.espncricinfo.com/rss/content/story/feeds/6.xml", "sports", "rss"),
        ("BBC Sport - Cricket", "https://feeds.bbci.co.uk/sport/cricket/rss.xml", "sports", "rss"),
        ("Yahoo Finance News", "https://finance.yahoo.com/news/rssindex", "business", "rss"),
        ("BBC News - Business", "https://feeds.bbci.co.uk/news/business/rss.xml", "business", "rss"),
        ("The Hindu BusinessLine", "https://www.thehindubusinessline.com/?service=rss", "business", "rss"),
        ("Telangana Today - Business", "https://telanganatoday.com/category/business/feed", "business", "rss"),
        ("Variety - Film", "https://variety.com/v/film/feed", "movies", "rss"),
        ("The Hollywood Reporter", "https://www.hollywoodreporter.com/feed", "movies", "rss"),
        ("Deadline Hollywood", "https://deadline.com/feed/rss", "movies", "rss"),
        ("Filmyfocus - Tollywood", "https://filmyfocus.com/feed", "movies", "rss"),
        ("Telugu Bulletin - Movies", "https://telugubulletin.com/movies/feed", "movies", "rss"),
        ("Telangana Today - Crime", "https://telanganatoday.com/category/crime/feed", "crime", "rss"),
        ("Telangana Today - Hyderabad", "https://telanganatoday.com/category/hyderabad/feed", "crime", "rss"),
        # --- new safe candidates (user-supplied) ---
        # Global
        ("The Guardian - World",       "https://www.theguardian.com/world/rss",                          "breaking", "rss"),
        ("The Guardian - India",       "https://www.theguardian.com/world/india/rss",                   "breaking", "rss"),
        ("The Guardian - Business",    "https://www.theguardian.com/business/rss",                      "business", "rss"),
        ("The Guardian - Sport",       "https://www.theguardian.com/sport/rss",                         "sports", "rss"),
        ("The Guardian - Film",        "https://www.theguardian.com/film/rss",                          "movies", "rss"),
        ("VOA - Top Stories",          "https://www.voanews.com/api/zqboml-vomx-tpeivmy",                "breaking", "rss"),
        ("VOA - South & Central Asia", "https://www.voanews.com/api/z_-mqyl-vomx-tpevyvqv",              "breaking", "rss"),
        ("VOA - Economy",              "https://www.voanews.com/api/zyboql-vomx-tpetvmi",                "business", "rss"),
        ("VOA - Technology",           "https://www.voanews.com/api/zyritl-vomx-tpettmq",                "breaking", "rss"),
        ("NASA - Breaking News",       "https://www.nasa.gov/news-release/feed/",                       "breaking", "rss"),
        # India
        ("PIB - Press Releases",       "https://pib.gov.in/RssMain.aspx?ModId=6&Lang=1&Regid=3",       "breaking", "rss"),
    ]
]

# Channels that are known to stamp their logo/watermark on syndicated photos.
# This is a curated list of patterns that I've seen in real publisher feeds
# and that the logo-string heuristic in is_probably_logo_image() CANNOT catch
# (the heuristic only flags URL filenames containing "logo" etc.).
PUBLISHER_LOGO_DOMAINS = (
    # Big Indian TV / newspaper publisher CDNs that stamp logos.
    "static.toiimg.com",          # Times of India — big "TOI" watermark
    "timesofindia.indiatimes.com",
    "ndtvimg.com",                # NDTV — corner logo
    "images.hindustantimes.com",  # HT
    "static-img.hindustantimes.com",
    "bsmedia.business-standard.com",
    "images.indianexpress.com",
    "images.cnbctv18.com",
    "images.firstpost.com",
    "sakshi.com",                 # Sakshi — channel watermark
    "manatelangana.com",
    "ntnews.com",
    "123telugu.com",
    "andhrajyothy.com",
    "andhrajyothy.cache",
    "10tv.in",
    "ntv.co.in",
    "v6velugu.com",
    "v6velugu.net",
    "tv9telugu.com",
    "tv9.com",
    "bollywoodhungama.com",
    "static.feeds.indianexpress.com",
    "images.moneycontrol.com",
    "mcweb/mcimages",
    "akamaicdn",
    "cdn.gulte.com",
    "gulte.com",
    "telugubulletin.com/wp-content",
    "teluguone.com",
    "thehansindia.com",
    "deccanchronicle.com",
    "deccanherald.com",
)

# Curated list of CDNs/hosts whose images are public-domain, Creative
# Commons, or US-Government / public-broadcaster sourced. Adding a host here
# means `is_publisher_stamped()` will return False for it. The default
# heuristic is still applied (filename flags), so logos uploaded with
# explicit "logo" in the URL are still caught.
SAFE_IMAGE_HOSTS = (
    "gdb.voanews.com",            # Voice of America — public-domain US gov
    "i.guim.co.uk",               # The Guardian image CDN (free to use w/ credit)
    "media.guim.co.uk",
    "images-assets.nasa.gov",     # NASA — public domain
    "www.nasa.gov",
    "pbs.twimg.com",              # Twitter syndication (used by PIB/DD News)
    "pib.gov.in",                 # Press Information Bureau — Indian govt
    "pibimg.nic.in",              # PIB image hosting
    "ddnews.gov.in",
    "prasarbharati.gov.in",
    "newsonair.gov.in",
    "isro.gov.in",
    "dipr.telangana.gov.in",
)

HEADERS = scraper.HEADERS
TIMEOUT_FEED = 10
TIMEOUT_PAGE = 6
SAMPLE = 6  # entries per channel

# Heuristic flags (in addition to scraper.is_probably_logo_image).
SHORT_DOMAIN_HOSTS_HINT = False  # placeholder for future tuning


def is_publisher_stamped(url: str) -> bool:
    """True if the image's host matches a known publisher-stamped domain.

    SAFE_IMAGE_HOSTS short-circuit this: government / public-broadcaster /
    public-domain CDNs (VOA, NASA, PIB, Guardian CDN) return False even if
    they would otherwise look like a publisher host.
    """
    if not url:
        return False
    try:
        host = urlparse(url).netloc.lower()
    except Exception:
        return False
    if any(h in host for h in SAFE_IMAGE_HOSTS):
        return False
    return any(d in host for d in PUBLISHER_LOGO_DOMAINS)


def classify_image(url: str) -> str:
    """Return one of: CLEAN, LOGO_URL, PUBLISHER_STAMP, EMPTY."""
    if not url:
        return "EMPTY"
    if scraper.is_probably_logo_image(url):
        return "LOGO_URL"
    if is_publisher_stamped(url):
        return "PUBLISHER_STAMP"
    return "CLEAN"


def fetch_feed_entries(url: str):
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT_FEED)
        r.raise_for_status()
    except Exception as e:
        return None, f"feed error: {e!r}"
    return feedparser.parse(r.text).entries, None


def rss_image_for_entry(entry) -> str:
    """Best RSS-level image URL for an entry, or empty string."""
    try:
        if hasattr(entry, "media_content") and entry.media_content:
            return (entry.media_content[0].get("url") or "").strip()
        if hasattr(entry, "media_thumbnail") and entry.media_thumbnail:
            return (entry.media_thumbnail[0].get("url") or "").strip()
        for link in getattr(entry, "links", []) or []:
            if (link.get("type") or "").startswith("image/"):
                return (link.get("href") or "").strip()
        for enc in getattr(entry, "enclosures", []) or []:
            if (enc.get("type") or "").startswith("image/"):
                return (enc.get("href") or "").strip()
        html_blob = (getattr(entry, "summary", "") or "") + " " + (
            (getattr(entry, "content", [{}])[0].get("value", "") if getattr(entry, "content", None) else "") or ""
        )
        if html_blob.strip():
            soup = BeautifulSoup(html_blob, "html.parser")
            img = soup.find("img")
            if img and img.get("src"):
                return img["src"].strip()
    except Exception:
        return ""
    return ""


def page_image_for_article(url: str) -> str:
    """Fetch the article HTML and extract og:image / twitter:image / first img."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT_PAGE)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        og = soup.find("meta", property="og:image")
        if og and og.get("content"):
            return og["content"].strip()
        tw = soup.find("meta", attrs={"name": "twitter:image"})
        if tw and tw.get("content"):
            return tw["content"].strip()
        img = soup.find("img")
        if img and img.get("src"):
            return img["src"].strip()
    except Exception:
        return ""
    return ""


def audit_channel(src: dict) -> dict:
    name = src["name"]
    url = src["url"]
    category = src.get("category", "?")
    blocked = scraper.has_image_risk(name)

    entries, err = fetch_feed_entries(url)
    if err or not entries:
        return {
            "name": name,
            "category": category,
            "url": url,
            "blocked_by_policy": blocked,
            "status": "DEAD",
            "total": 0,
            "clean": 0,
            "logo_url": 0,
            "publisher_stamp": 0,
            "empty": 0,
            "sample_images": [],
        }

    sample = entries[:SAMPLE]
    counts = {"clean": 0, "logo_url": 0, "publisher_stamp": 0, "empty": 0}
    sample_images = []

    for e in sample:
        img = rss_image_for_entry(e)
        if not img:
            # Try the article page
            link = (getattr(e, "link", "") or "").strip()
            if link:
                img = page_image_for_article(link)
        verdict = classify_image(img)
        if verdict == "CLEAN":
            counts["clean"] += 1
        elif verdict == "LOGO_URL":
            counts["logo_url"] += 1
        elif verdict == "PUBLISHER_STAMP":
            counts["publisher_stamp"] += 1
        else:
            counts["empty"] += 1
        sample_images.append((verdict, img))

    risky = counts["logo_url"] + counts["publisher_stamp"]
    if risky == 0 and counts["empty"] == len(sample):
        status = "NO_IMAGES"
    elif risky == 0:
        status = "CLEAN"
    elif risky >= len(sample) // 2 + 1:
        status = "RISKY"
    else:
        status = "MIXED"

    return {
        "name": name,
        "category": category,
        "url": url,
        "blocked_by_policy": blocked,
        "status": status,
        "total": len(sample),
        **counts,
        "sample_images": sample_images,
    }


def main():
    print(f"Auditing {len(ALL_SOURCES_RAW)} channels live (sample {SAMPLE} entries each)...\n")
    results = []
    for s in ALL_SOURCES_RAW:
        try:
            r = audit_channel(s)
        except Exception as e:
            r = {"name": s["name"], "category": s.get("category", "?"), "url": s["url"],
                 "blocked_by_policy": scraper.has_image_risk(s["name"]),
                 "status": "ERROR", "total": 0, "clean": 0, "logo_url": 0,
                 "publisher_stamp": 0, "empty": 0, "sample_images": [],
                 "error": repr(e)}
        results.append(r)
        # live progress
        print(f"  {r['status']:<11} {r.get('clean',0):>2}/{r.get('total',0):<2} clean   "
              f"{r.get('logo_url',0):>2} logo-url   {r.get('publisher_stamp',0):>2} stamped   "
              f"{r.get('empty',0):>2} empty   {r['name']}")

    # Bucket summary
    by_status = {"CLEAN": [], "RISKY": [], "MIXED": [], "NO_IMAGES": [], "DEAD": [], "ERROR": []}
    for r in results:
        by_status.setdefault(r["status"], []).append(r)

    print("\n" + "=" * 78)
    print("SUMMARY")
    print("=" * 78)
    total = len(results)
    blocked_count = sum(1 for r in results if r["blocked_by_policy"])
    print(f"Total channels defined in scraper.py : {total}")
    print(f"Already blocked by source_policy.py  : {blocked_count}")
    print(f"Audit status buckets (post block):")
    for k in ("CLEAN", "NO_IMAGES", "MIXED", "RISKY", "DEAD", "ERROR"):
        print(f"   {k:<11}: {len(by_status.get(k, []))}  -> {[r['name'] for r in by_status.get(k, [])]}")

    # Channels that are CLEAN and NOT blocked — the safe keepers.
    safe = [r["name"] for r in results if r["status"] == "CLEAN" and not r["blocked_by_policy"]]
    print(f"\nSAFE TO KEEP (clean images, not blocked): {len(safe)}")
    for n in safe:
        print(f"   + {n}")

    # Channels that are RISKY or MIXED — drop candidates.
    drop = [r["name"] for r in results if r["status"] in ("RISKY", "MIXED")]
    print(f"\nDROP CANDIDATES (risky/mixed images): {len(drop)}")
    for n in drop:
        print(f"   x {n}")

    # No-image channels (likely not blocked, just RSS doesn't expose images)
    no_img = [r["name"] for r in results if r["status"] == "NO_IMAGES" and not r["blocked_by_policy"]]
    print(f"\nNO RSS IMAGES (manual decision needed): {len(no_img)}")
    for n in no_img:
        print(f"   ? {n}")

    # Save JSON for the user
    out = os.path.join(HERE, "image_audit_report.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"\nFull JSON report: {out}")


if __name__ == "__main__":
    main()
