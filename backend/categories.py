"""Single source of truth for news categories.

Both the API (`main.py`) and the scraper (`scraper.py`) import from here.
Add a new category in exactly one place: append to ``VALID_CATEGORIES``
and (optionally) extend ``SOURCE_CATEGORY_MAP`` so source-based bucketing
works.
"""

from __future__ import annotations

# Categories that the API will accept and that the scraper will produce.
# Order matters for any UI iteration that respects it.
VALID_CATEGORIES: frozenset[str] = frozenset(
    {"breaking", "sports", "business", "movies", "crime"}
)

# Sentinel category for content we want to drop (junk/horoscope/recipe/etc.).
# Not exposed via the API.
IGNORE_CATEGORY = "ignore"

DEFAULT_CATEGORY = "breaking"

# Source name -> category. Matching is case-insensitive substring on the
# stored ``source`` column. Keys are lowercase.
SOURCE_CATEGORY_MAP: dict[str, str] = {
    # sports
    "bbc sport": "sports",
    "espn": "sports",
    "sportstar": "sports",
    "cricbuzz": "sports",
    "cricinfo": "sports",
    "goal": "sports",
    "mykhel": "sports",
    # movies
    "123telugu": "movies",
    "greatandhra": "movies",
    "tollywood": "movies",
    "filmibeat": "movies",
    "pinkvilla": "movies",
    "deadline": "movies",
    "hollywoodreporter": "movies",
    "hollywood reporter": "movies",
    # business
    "cnbc": "business",
    "economictimes": "business",
    "economic times": "business",
    "moneycontrol": "business",
    "bloomberg": "business",
    "reuters": "business",
    # breaking (default bucket)
    "aljazeera": "breaking",
    "al jazeera": "breaking",
    "tv9": "breaking",
    "ntv": "breaking",
    "v6velugu": "breaking",
    "v6 velugu": "breaking",
    "telugu360": "breaking",
    "bbc": "breaking",
    "cnn": "breaking",
    "india today": "breaking",
    "ndtv": "breaking",
    "the hindu": "breaking",
    "times of india": "breaking",
    "indianexpress": "breaking",
    "indian express": "breaking",
    "manatelangana": "breaking",
}


def is_valid(category: str | None) -> bool:
    """Return True if ``category`` is one of the exposed categories."""
    if not category:
        return False
    return category.lower().strip() in VALID_CATEGORIES


def normalize(category: str | None) -> str:
    """Coerce a free-form category string into a known one, or default.

    Handles common aliases to match frontend's normalizeCategory():
    - finance, business & finance, market, technology, tech → business
    - entertainment, movie, film, cinema → movies
    - sport, cricket → sports
    - crime, police → crime
    """
    if not category:
        return DEFAULT_CATEGORY

    cat = category.lower().strip()

    if cat in VALID_CATEGORIES:
        return cat

    # Business/finance aliases
    if cat in ("finance", "business & finance"):
        return "business"
    if any(kw in cat for kw in ("business", "finance", "market", "technology", "tech")):
        return "business"

    # Movies/entertainment aliases
    if cat in ("entertainment", "movie"):
        return "movies"
    if any(kw in cat for kw in ("film", "cinema", "movie", "entertainment")):
        return "movies"

    # Sports aliases
    if cat == "sport":
        return "sports"
    if any(kw in cat for kw in ("sport", "cricket")):
        return "sports"

    # Crime aliases
    if any(kw in cat for kw in ("crime", "police")):
        return "crime"

    return DEFAULT_CATEGORY


def from_source(source: str | None) -> str:
    """Best-effort category from the source name alone.

    Uses longest-match-first so that a more specific source name
    (e.g. "V6 Velugu Crime") wins over a generic prefix
    (e.g. "V6 Velugu"). The scraper also tags articles with the
    right category at fetch time, so this is a fallback only.
    """
    if not source:
        return DEFAULT_CATEGORY
    src = source.lower().strip()
    # Sort by descending key length so longer/more specific keys win.
    for key, cat in sorted(
        SOURCE_CATEGORY_MAP.items(), key=lambda kv: len(kv[0]), reverse=True
    ):
        if key in src:
            return cat
    return DEFAULT_CATEGORY


def resolve(stored: str | None, source: str | None) -> str:
    """Pick the final category: prefer stored (if valid), else infer from source."""
    if is_valid(stored):
        return stored.lower().strip()
    return from_source(source)
