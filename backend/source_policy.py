"""Source policy shared by the API, the scraper, and the audit tooling.

Two independent axes — do not conflate them again:

  1. IMAGE RISK  (``has_image_risk``)
     "This publisher's PHOTOS are copyright-risky." Governs IMAGES ONLY:
     watermarked, logo-stamped, or syndicated wire imagery that we must not
     re-host. The correct response is to drop the image and keep the text.

  2. INGEST/SERVE BAN  (``is_blocked_source``)
     "We never want this publisher's rows in the database or in /news at all."
     Currently EMPTY — nothing is banned outright.

The previous single-axis version used one predicate (``BLOCKED_SOURCE_KEYWORDS``)
for both meanings and applied it at import time, at ingest time, AND at serve
time. That made the module silently unsatisfiable: adding a Telugu-language
*text* source such as Sakshi or Andhra Jyothy was impossible, because rows would
be ingested and then invisibly filtered out of /news by the same keyword list
that only ever meant "their pictures are risky". Splitting the predicate is the
whole point of this module.
"""

from __future__ import annotations


# =========================
# EXACT-NAME CARVE-OUT
# =========================
# Exact (lowercased, stripped) source names that are exempt from the image-risk
# keyword scan. These publishers' feeds carry their own editorial photography
# that we have manually cleared.
#
# NOTE: "sportstar - the hindu" survives ONLY because of this allowlist — the
# image-risk list holds "the hindu" as a *substring* keyword, so without the
# exact-name carve-out the Sportstar feed would be flagged by it.
ALLOWED_SOURCE_NAMES = {
    "espncricinfo - india team",
    "sportstar - the hindu",
}


# =========================
# AXIS 1 — IMAGE RISK
# =========================
# Substring matches for publishers whose feeds commonly include publisher-owned,
# logo-stamped, or syndicated imagery. Matching here means "strip/skip the
# image", NOT "reject the article".
IMAGE_RISK_SOURCE_KEYWORDS = (
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

# DEPRECATED alias kept so older imports of the pre-split name keep working.
# It has always meant "image risk" — never an ingest/serve ban. Prefer
# IMAGE_RISK_SOURCE_KEYWORDS in new code.
BLOCKED_SOURCE_KEYWORDS = IMAGE_RISK_SOURCE_KEYWORDS


# =========================
# AXIS 2 — INGEST/SERVE BAN
# =========================
# Publishers we genuinely do not want at all — content-quality, licensing, or
# legal reasons, not photo watermarks. Deliberately EMPTY: every entry here
# removes a publisher's text from the site, so additions need a real reason.
BANNED_SOURCE_KEYWORDS: tuple[str, ...] = ()


# =========================
# PREDICATES
# =========================
def _matches(source: str | None, keywords: tuple[str, ...]) -> bool:
    """True if ``source`` contains any of ``keywords`` (case-insensitive)."""
    lowered = (source or "").lower().strip()
    return bool(lowered) and any(keyword in lowered for keyword in keywords)


def has_image_risk(source: str | None) -> bool:
    """True if this publisher's IMAGES are copyright-risky.

    Callers should drop/replace the image and keep the article text. The
    ALLOWED_SOURCE_NAMES exact-name carve-out wins over any keyword match.
    """
    lowered = (source or "").lower().strip()
    if lowered in ALLOWED_SOURCE_NAMES:
        return False
    return _matches(lowered, IMAGE_RISK_SOURCE_KEYWORDS)


def is_blocked_source(source: str | None) -> bool:
    """True if this publisher must never be ingested or served.

    Matches BANNED_SOURCE_KEYWORDS only — image risk is a separate axis, see
    ``has_image_risk``. With BANNED_SOURCE_KEYWORDS empty this returns False
    for every source, which is intentional.
    """
    return _matches(source, BANNED_SOURCE_KEYWORDS)
