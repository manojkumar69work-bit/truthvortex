"""Probe alternate feed URLs for sources that didn't return RSS on first try."""
import requests, sys

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "application/rss+xml, application/xml, text/xml, */*",
}

CANDIDATES = [
    # VOA — try common patterns
    ("VOA - top",      "https://www.voanews.com/rss/news.xml",                                    "breaking"),
    ("VOA - world",    "https://www.voanews.com/rss/world.xml",                                   "breaking"),
    ("VOA - all",      "https://www.voanews.com/rssfeeds",                                       "breaking"),
    # Wikinews
    ("Wikinews - alt", "https://en.wikinews.org/w/index.php?title=Special:NewsFeed&feed=atom&count=30", "breaking"),
    # EC press corner
    ("EC press en",    "https://ec.europa.eu/commission/presscorner/api/feed/press-releases/en",  "breaking"),
    ("EC press all",   "https://ec.europa.eu/commission/presscorner/api/rss/pressreleases",       "breaking"),
    # DD News
    ("DD News wp",     "https://ddnews.gov.in/?feed=rss2",                                       "breaking"),
    ("DD News wp-json","https://ddnews.gov.in/wp-json/wp/v2/posts?per_page=10",                   "breaking"),
    # Prasar Bharati
    ("Prasar wp",      "https://prasarbharati.gov.in/?feed=rss2",                                 "breaking"),
    # AIR
    ("AIR wp",         "https://newsonair.gov.in/?feed=rss2",                                     "breaking"),
    ("AIR alt",        "https://newsonair.gov.in/RSS.aspx",                                      "breaking"),
    # ISRO
    ("ISRO wp",        "https://www.isro.gov.in/?feed=rss2",                                      "breaking"),
    # DIPR Telangana
    ("DIPR wp",        "https://dipr.telangana.gov.in/?feed=rss2",                                "breaking"),
    # T-Hub
    ("T-Hub wp",       "https://t-hub.co/?feed=rss2",                                             "breaking"),
    # WE-Hub
    ("WE-Hub wp",      "https://we-hub.org/?feed=rss2",                                           "breaking"),
    # Hyderabad Police
    ("Hyd Police wp",  "https://www.hyderabadpolice.gov.in/?feed=rss2",                           "crime"),
    # Telangana Today - try the alternate paths
    ("TT main",        "https://telanganatoday.com/feed/",                                        "breaking"),
    ("TT wp",          "https://telanganatoday.com/?feed=rss2",                                   "breaking"),
    ("TT wp-json",     "https://telanganatoday.com/wp-json/wp/v2/posts?per_page=10",              "breaking"),
    ("TT business",    "https://telanganatoday.com/category/business/feed",                      "business"),
    ("TT crime",       "https://telanganatoday.com/category/crime/feed",                         "crime"),
    ("TT hyderabad",   "https://telanganatoday.com/category/hyderabad/feed",                     "crime"),
]

def probe(name, url, cat):
    try:
        r = requests.get(url, headers=HEADERS, timeout=10, allow_redirects=True)
        ct = (r.headers.get("content-type") or "").lower()
        size = len(r.text or "")
        # be lenient: an HTML page >5KB with <rss or <feed is also "looks like feed"
        is_xml = ("xml" in ct) or ("rss" in ct) or ("atom" in ct) or url.endswith((".rss", ".xml"))
        is_html_with_feed = ("html" in ct) and size > 2000 and (b"<rss" in r.content or b"<feed" in r.content or b"<channel" in r.content)
        return {
            "name": name, "cat": cat, "url": url,
            "status": r.status_code, "ct": ct, "size": size,
            "is_xml": is_xml, "is_html_with_feed": is_html_with_feed,
        }
    except Exception as e:
        return {"name": name, "cat": cat, "url": url, "error": repr(e)[:80]}

results = [probe(*c) for c in CANDIDATES]
for r in results:
    if "error" in r:
        print(f"  ERR   {r['cat']:<10}  {r['name']:<22}  {r['url']}  -> {r['error']}")
    else:
        ok = (r["status"]==200 and (r["is_xml"] or r["is_html_with_feed"]) and r["size"]>500)
        flag = "OK " if ok else ".. "
        hint = "FEED" if r["is_html_with_feed"] else ("XML" if r["is_xml"] else "HTML")
        print(f"  {flag}  {r['status']}  {r['ct'][:20]:<20}  {r['size']:>6}b  {hint:<4}  {r['cat']:<10}  {r['name']:<22}  {r['url']}")
