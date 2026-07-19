"""Probe candidate RSS feed URLs and report status."""
import requests, sys

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "application/rss+xml, application/xml, text/xml, */*",
}

CANDIDATES = [
    # Global
    ("The Guardian - World",       "https://www.theguardian.com/world/rss",                                          "breaking"),
    ("The Guardian - US",         "https://www.theguardian.com/us/rss",                                            "breaking"),
    ("The Guardian - India",      "https://www.theguardian.com/world/india/rss",                                   "breaking"),
    ("The Guardian - Business",   "https://www.theguardian.com/business/rss",                                      "business"),
    ("The Guardian - Sport",      "https://www.theguardian.com/sport/rss",                                         "sports"),
    ("The Guardian - Film",       "https://www.theguardian.com/film/rss",                                          "movies"),
    ("VOA - RSS top",             "https://www.voanews.com/rssfeeds",                                              "breaking"),
    ("VOA - World",               "https://www.voanews.com/api/zqomeve_keq",                                       "breaking"),
    ("Wikinews - Main",           "https://en.wikinews.org/w/index.php?title=Special:NewsFeed&feed=atom&categories=Published&namespace=0&count=30", "breaking"),
    ("NASA - Breaking News",      "https://www.nasa.gov/news-release/feed/",                                       "breaking"),
    ("European Commission - News","https://ec.europa.eu/commission/presscorner/api/feed/press-releases/en/rss",     "breaking"),
    # India
    ("PIB - Press Releases",      "https://pib.gov.in/RssMain.aspx?ModId=6&Lang=1&Regid=3",                      "breaking"),
    ("DD News",                   "https://ddnews.gov.in/feed/",                                                   "breaking"),
    ("Prasar Bharati News",       "https://prasarbharati.gov.in/feed/",                                            "breaking"),
    ("All India Radio - Top",     "https://newsonair.gov.in/Rss.aspx?type=1",                                      "breaking"),
    ("ISRO News",                 "https://www.isro.gov.in/media-isro/media/rss.xml",                              "breaking"),
    ("Telangana DIPR",            "https://dipr.telangana.gov.in/feed/",                                           "breaking"),
    ("Hyderabad City Police",     "https://www.hyderabadpolice.gov.in/feed/",                                      "crime"),
    # Telangana
    ("T-Hub",                     "https://t-hub.co/feed/",                                                        "breaking"),
    ("WE-Hub",                    "https://we-hub.org/feed/",                                                      "breaking"),
]

def probe(name, url, cat):
    try:
        r = requests.get(url, headers=HEADERS, timeout=10, allow_redirects=True)
        ct = (r.headers.get("content-type") or "").lower()
        ok_status = r.status_code == 200
        is_xml = ("xml" in ct) or ("rss" in ct) or ("atom" in ct) or url.endswith((".rss", ".xml"))
        size = len(r.text or "")
        return {
            "name": name, "cat": cat, "url": url,
            "status": r.status_code, "ct": ct, "size": size,
            "is_xml": is_xml,
        }
    except Exception as e:
        return {"name": name, "cat": cat, "url": url, "error": repr(e)}

results = [probe(*c) for c in CANDIDATES]
for r in results:
    if "error" in r:
        print(f"  ERR    {r['cat']:<10}  {r['name']:<35}  {r['url']}  -> {r['error'][:60]}")
    else:
        flag = "OK " if (r["status"]==200 and r["is_xml"] and r["size"]>200) else ".. "
        print(f"  {flag}  {r['status']}  {r['ct'][:25]:<25}  {r['size']:>6}b  {r['cat']:<10}  {r['name']:<35}  {r['url']}")
