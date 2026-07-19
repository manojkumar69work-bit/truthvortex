"""Source safety policy shared by the API and scraper."""

from __future__ import annotations


# Exact/substring matches for sources we do not want to ingest or serve.
# These are mostly TV channels, newspapers, and entertainment portals whose
# feeds commonly include publisher-owned, logo-stamped, or syndicated imagery.
ALLOWED_SOURCE_NAMES = {
    "espncricinfo - india team",
    "sportstar - the hindu",
}

BLOCKED_SOURCE_KEYWORDS = (
    "10tv",
    "123telugu",
    "andhra jyothy",
    "bollywood hungama",
    "businessline",
    "cnbc",
    "collider",
    "deadline",
    "economic times",
    "economictimes",
    "espn",
    "filmibeat",
    "filmyfocus",
    "greatandhra",
    "hollywood reporter",
    "hollywoodreporter",
    "indianexpress",
    "indian express",
    "livemint",
    "mana telangana",
    "manatelangana",
    "namasthe telangana",
    "nava telangana",
    "ndtv",
    "ntv",
    "oneindia",
    "sakshi",
    "screen rant",
    "sportstar",
    "telugu bulletin",
    "the hindu",
    "times of india",
    "timesofindia",
    "toi",
    "tv9",
    "v6",
    "variety",
    "visala andhra",
    "wired",
)


def is_blocked_source(source: str | None) -> bool:
    lowered = (source or "").lower().strip()
    if lowered in ALLOWED_SOURCE_NAMES:
        return False
    return bool(lowered) and any(
        keyword in lowered for keyword in BLOCKED_SOURCE_KEYWORDS
    )
