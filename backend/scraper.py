import logging
import os

# Configure module-level logger; the `log()` shim below keeps every existing
# callsite working without changes while routing output through stdlib logging.
logger = logging.getLogger("truthvortex.scraper")
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(_handler)
    logger.setLevel(os.getenv("LOG_LEVEL", "INFO").upper())
    logger.propagate = False
import re
import threading
import time
import html
import calendar
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
import feedparser

from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from rapidfuzz import fuzz
from dotenv import load_dotenv
from openai import OpenAI

import categories as cats
from source_policy import is_blocked_source
from db import get_cursor


# =========================
# ENV SETUP
# =========================
load_dotenv()

# ----- Multi-provider fallback chain -----
# Define all providers in priority order. Each has a name, api_key env var,
# base_url, model, and an optional override for key / url / model.
# When one hits rate limits, the next in chain is tried automatically.
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY") or os.getenv("NVAPI_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
# OpenRouter — two keys supported for redundancy (rotates on rate limit).
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_API_KEY_2 = os.getenv("OPENROUTER_API_KEY_2")

# Default primary provider is OpenRouter (free gemma instruction-tuned model
# gives clean Telugu with no reasoning-trace leakage); Groq is the fallback.
REQUESTED_PROVIDER = os.getenv("AI_PROVIDER", "openrouter").strip().lower()
_OVERRIDE_KEY = os.getenv("AI_API_KEY")


def _provider_model(provider: str, default: str) -> str:
    specific = os.getenv(f"{provider.upper()}_MODEL")
    if specific:
        return specific
    if REQUESTED_PROVIDER == provider and os.getenv("AI_MODEL"):
        return os.getenv("AI_MODEL", default)
    return default


def _provider_base_url(provider: str, default: str) -> str:
    specific = os.getenv(f"{provider.upper()}_BASE_URL")
    if specific:
        return specific
    if REQUESTED_PROVIDER == provider and os.getenv("AI_BASE_URL"):
        return os.getenv("AI_BASE_URL", default)
    return default


_OPENROUTER_BASE = "https://openrouter.ai/api/v1"
# Instruction-tuned (not a reasoning model) so no <think> traces leak into the
# Telugu summary. Override with OPENROUTER_MODEL if needed.
_OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "google/gemma-4-26b-a4b-it:free")

PROVIDERS_BY_NAME = {}
if OPENROUTER_API_KEY:
    PROVIDERS_BY_NAME["openrouter"] = {
        "name": "openrouter",
        "api_key": _OVERRIDE_KEY or OPENROUTER_API_KEY,
        "base_url": _provider_base_url("openrouter", _OPENROUTER_BASE),
        "model": _provider_model("openrouter", _OPENROUTER_MODEL),
    }
if OPENROUTER_API_KEY_2:
    PROVIDERS_BY_NAME["openrouter2"] = {
        "name": "openrouter2",
        "api_key": OPENROUTER_API_KEY_2,
        "base_url": os.getenv("OPENROUTER_BASE_URL", _OPENROUTER_BASE),
        "model": _OPENROUTER_MODEL,
    }
if NVIDIA_API_KEY:
    PROVIDERS_BY_NAME["nvidia"] = {
        "name": "nvidia",
        "api_key": _OVERRIDE_KEY or NVIDIA_API_KEY,
        "base_url": _provider_base_url("nvidia", "https://integrate.api.nvidia.com/v1"),
        "model": _provider_model("nvidia", "nvidia/llama-3.3-nemotron-super-49b-v1.5"),
    }
if GROQ_API_KEY:
    PROVIDERS_BY_NAME["groq"] = {
        "name": "groq",
        "api_key": _OVERRIDE_KEY or GROQ_API_KEY,
        "base_url": _provider_base_url("groq", "https://api.groq.com/openai/v1"),
        "model": _provider_model("groq", "meta-llama/llama-4-scout-17b-16e-instruct"),
    }
if GEMINI_API_KEY and GEMINI_API_KEY.startswith("AIza"):
    PROVIDERS_BY_NAME["gemini"] = {
        "name": "gemini",
        "api_key": _OVERRIDE_KEY or GEMINI_API_KEY,
        "base_url": _provider_base_url("gemini", "https://generativelanguage.googleapis.com/v1beta/openai/"),
        "model": _provider_model("gemini", "models/gemini-2.5-flash"),
    }

PROVIDERS = []
for provider_name in [REQUESTED_PROVIDER, "openrouter", "openrouter2", "nvidia", "groq", "gemini"]:
    provider = PROVIDERS_BY_NAME.get(provider_name)
    if provider and provider not in PROVIDERS:
        PROVIDERS.append(provider)

if not PROVIDERS:
    # Fallback: try to read old-style single env vars
    PROVIDERS.append({
        "name": "custom",
        "api_key": os.getenv("AI_API_KEY", ""),
        "base_url": os.getenv("AI_BASE_URL", "https://api.groq.com/openai/v1"),
        "model": os.getenv("AI_MODEL", "llama-3.3-70b-versatile"),
    })

_ACTIVE_PROVIDER_IDX = 0
_EXHAUSTED_PROVIDERS = set()


def _current_provider() -> dict:
    """Return the currently active provider config."""
    return PROVIDERS[_ACTIVE_PROVIDER_IDX]


_PROVIDER_LOCK = threading.Lock()


def _next_provider() -> bool:
    """Move to the next non-exhausted provider. Updates globals. Returns False if none left."""
    global _ACTIVE_PROVIDER_IDX, AI_PROVIDER, AI_API_KEY, AI_BASE_URL, AI_MODEL, ai_client
    with _PROVIDER_LOCK:
        _EXHAUSTED_PROVIDERS.add(_ACTIVE_PROVIDER_IDX)
        for i in range(len(PROVIDERS)):
            if i in _EXHAUSTED_PROVIDERS:
                continue
            # Skip providers whose client never initialized — switching to a
            # None client would AttributeError on the next call.
            if AI_CLIENTS.get(PROVIDERS[i]["name"]) is None:
                _EXHAUSTED_PROVIDERS.add(i)
                continue
            _ACTIVE_PROVIDER_IDX = i
            p = PROVIDERS[i]
            AI_PROVIDER = p["name"]
            AI_API_KEY = p["api_key"]
            AI_BASE_URL = p["base_url"]
            AI_MODEL = p["model"]
            ai_client = AI_CLIENTS.get(p["name"])
            log(f"    [Provider] Switched to {p['name']} ({p['model']})")
            return True
    log("    [Provider] All providers exhausted.")
    return False


def _reset_providers():
    """Reset exhausted state for a new run."""
    global _ACTIVE_PROVIDER_IDX, _EXHAUSTED_PROVIDERS
    _ACTIVE_PROVIDER_IDX = 0
    _EXHAUSTED_PROVIDERS = set()


AI_PROVIDER = _current_provider()["name"]
AI_API_KEY = _current_provider()["api_key"]
AI_BASE_URL = _current_provider()["base_url"]
AI_MODEL = _current_provider()["model"]

ENABLE_TRANSLATION = os.getenv("ENABLE_TRANSLATION", "false").lower() == "true"
ENABLE_AI_SUMMARY = os.getenv("ENABLE_AI_SUMMARY", "true").lower() == "true"
# Requirement: every generated article must have an AI headline and 5-8 line
# AI summary written directly in Telugu. This is intentionally not env-driven.
SUMMARY_LANGUAGE = "Telugu"

MAX_ENTRIES_PER_SOURCE = int(os.getenv("MAX_ENTRIES_PER_SOURCE", "6"))
# All sources are copyright-safe — run sequentially to avoid Groq API rate limits.
MAX_CONCURRENT_SOURCES = int(os.getenv("MAX_CONCURRENT_SOURCES", "1"))

REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "12"))
PAGE_IMAGE_TIMEOUT = int(os.getenv("PAGE_IMAGE_TIMEOUT", "6"))
ARTICLE_TEXT_TIMEOUT = int(os.getenv("ARTICLE_TEXT_TIMEOUT", "10"))

MIN_FULL_ARTICLE_CHARS = int(os.getenv("MIN_FULL_ARTICLE_CHARS", "250"))
MIN_AI_INPUT_CHARS = int(os.getenv("MIN_AI_INPUT_CHARS", "80"))
MIN_AI_SUMMARY_CHARS = int(os.getenv("MIN_AI_SUMMARY_CHARS", "40"))
# Spec: AI summaries must be 5-8 lines in Telugu as a flowing paragraph.
MIN_AI_SUMMARY_LINES = int(os.getenv("MIN_AI_SUMMARY_LINES", "5"))
MAX_AI_SUMMARY_LINES = int(os.getenv("MAX_AI_SUMMARY_LINES", "8"))

# Categories that the AI should be called for. Falls back to the
# canonical set from categories.py so the two can't drift apart.
_env_ai_cats = {
    item.strip().lower()
    for item in os.getenv(
        "AI_TARGET_CATEGORIES",
        ",".join(sorted(cats.VALID_CATEGORIES)),
    ).split(",")
    if item.strip()
}
AI_TARGET_CATEGORIES = _env_ai_cats & cats.VALID_CATEGORIES

SKIP_PAGE_IMAGE_EXTRACTION = (
    os.getenv("SKIP_PAGE_IMAGE_EXTRACTION", "false").lower() == "true"
)


# =========================
# LOGGING
# =========================
def log(message: str = ""):
    # Backwards-compatible shim: routes to stdlib logging so cron output is
    # structured/level-filterable on Render, while every existing callsite
    # (still 30+ uses of `log(...)`) keeps working unchanged.
    logger.info(message)


# =========================
# OPTIONAL TRANSLATION
# =========================
translator = None

if ENABLE_TRANSLATION:
    try:
        from deep_translator import GoogleTranslator

        translator = GoogleTranslator(source="auto", target="te")
        log("• Translation enabled")
    except Exception as e:
        translator = None
        log(f"• Translation disabled ({e})")
else:
    log("• Translation disabled")


# =========================
# AI CLIENTS (one per provider)
# =========================
AI_CLIENTS: dict[str, OpenAI | None] = {}

for p in PROVIDERS:
    try:
        AI_CLIENTS[p["name"]] = OpenAI(
            base_url=p["base_url"],
            api_key=p["api_key"],
        )
        log(f"  ✓ Client created: {p['name']} ({p['model']})")
    except Exception as e:
        AI_CLIENTS[p["name"]] = None
        log(f"  ✗ Client failed: {p['name']} ({e})")

ai_client = AI_CLIENTS.get(_current_provider()["name"])
_has_any_client = any(v is not None for v in AI_CLIENTS.values())

log(f"• Providers: {[p['name'] for p in PROVIDERS]}")
log(f"• Active: {_current_provider()['name']} ({AI_MODEL})")
log(f"• ENABLE_AI_SUMMARY: {ENABLE_AI_SUMMARY}")
log(f"• Any AI client available: {_has_any_client}")
log("• MAX_AI_SUMMARIES_PER_RUN: unlimited")
log(f"• MAX_ENTRIES_PER_SOURCE: {MAX_ENTRIES_PER_SOURCE}")
log(f"• AI_TARGET_CATEGORIES: {AI_TARGET_CATEGORIES}")
log(f"• SKIP_PAGE_IMAGE_EXTRACTION: {SKIP_PAGE_IMAGE_EXTRACTION}")
log(f"• MIN_FULL_ARTICLE_CHARS: {MIN_FULL_ARTICLE_CHARS}")
log(f"• MIN_AI_INPUT_CHARS: {MIN_AI_INPUT_CHARS}")
log(f"• MIN_AI_SUMMARY_CHARS: {MIN_AI_SUMMARY_CHARS}")
log(f"• MAX_CONCURRENT_SOURCES: {MAX_CONCURRENT_SOURCES}")


# =========================
# CONFIG
# =========================
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "en-IN,en;q=0.9,te;q=0.8,hi;q=0.7,ta;q=0.6,kn;q=0.6,ml;q=0.6",
}

FALLBACK_NS_IMAGE = (
    "data:image/svg+xml;charset=UTF-8,"
    "%3Csvg xmlns='http://www.w3.org/2000/svg' width='1200' height='700' viewBox='0 0 1200 700'%3E"
    "%3Crect width='1200' height='700' fill='%23050b1a'/%3E"
    "%3Crect x='36' y='36' width='1128' height='628' rx='0' fill='%23071122' stroke='%231e293b' stroke-width='4'/%3E"
    "%3Ctext x='50%25' y='46%25' dominant-baseline='middle' text-anchor='middle' "
    "font-family='Arial, Helvetica, sans-serif' font-size='156' font-weight='900' fill='white'%3ETV%3C/text%3E"
    "%3Ctext x='50%25' y='61%25' dominant-baseline='middle' text-anchor='middle' "
    "font-family='Arial, Helvetica, sans-serif' font-size='42' font-weight='700' fill='%2394a3b8'%3ETruthVortex%3C/text%3E"
    "%3C/svg%3E"
)

# Image policy. The sources in this file are hand-curated to be free of
# publisher logos / watermarks, so by default the scraper KEEPS the real
# source photo (after passing it through the logo/junk-URL filter below).
# Set SAFE_IMAGES_ONLY=true to ignore all source images and always fall back
# to the built-in TruthVortex placeholder instead.
SAFE_IMAGES_ONLY = os.getenv("SAFE_IMAGES_ONLY", "false").lower() == "true"


# =========================
# SOURCES
# =========================
SOURCES = [
    # ============================================================
    # Copyright-safe / Clean image sources
    # ============================================================
    # --- breaking ---
    {
        "name": "UN News",
        "url": "https://news.un.org/feed/subscribe/en/news/all/rss.xml",
        "category": "breaking",
        "type": "rss",
    },
    {
        "name": "The Guardian - World",
        "url": "https://www.theguardian.com/world/rss",
        "category": "breaking",
        "type": "rss",
    },
    {
        "name": "Telangana Today",
        "url": "https://telanganatoday.com/feed",
        "category": "breaking",
        "type": "rss",
    },

    # --- sports ---
    {
        "name": "The Guardian - Sport",
        "url": "https://www.theguardian.com/sport/rss",
        "category": "sports",
        "type": "rss",
    },
    {
        "name": "Sportstar - The Hindu",
        "url": "https://sportstar.thehindu.com/feeder/default.rss",
        "category": "sports",
        "type": "rss",
    },
    {
        "name": "ESPNcricinfo - India Team",
        "url": "https://www.espncricinfo.com/rss/content/story/feeds/6.xml",
        "category": "sports",
        "type": "rss",
    },

    # --- business ---
    {
        "name": "The Guardian - Business",
        "url": "https://www.theguardian.com/business/rss",
        "category": "business",
        "type": "rss",
    },
    {
        "name": "Telangana Today - Business",
        "url": "https://telanganatoday.com/category/business/feed",
        "category": "business",
        "type": "rss",
    },

    # --- movies ---
    {
        "name": "The Guardian - Film",
        "url": "https://www.theguardian.com/film/rss",
        "category": "movies",
        "type": "rss",
    },
    {
        "name": "Telangana Today - Entertainment",
        "url": "https://telanganatoday.com/entertainment/feed",
        "category": "movies",
        "type": "rss",
    },

    # --- crime ---
    {
        "name": "The Guardian - Crime",
        "url": "https://www.theguardian.com/law/rss",
        "category": "crime",
        "type": "rss",
    },
    {
        "name": "Telangana Today - Crime",
        "url": "https://telanganatoday.com/category/crime/feed",
        "category": "crime",
        "type": "rss",
    },
    {
        "name": "Telangana Today - Hyderabad",
        "url": "https://telanganatoday.com/category/hyderabad/feed",
        "category": "crime",
        "type": "rss",
    },

    # ============================================================
    # Regional Telangana — verified clean (no logos/watermarks),
    # agency/PTI photos. Added to broaden regional coverage; The
    # Hans India also fills the regional SPORTS gap Telangana Today
    # can't (its sports feed is empty).
    # ============================================================
    {
        "name": "The Hans India - Telangana",
        "url": "https://www.thehansindia.com/rss/telangana",
        "category": "breaking",
        "type": "rss",
    },
    {
        "name": "The Hans India - Sports",
        "url": "https://www.thehansindia.com/rss/sports",
        "category": "sports",
        "type": "rss",
    },
    {
        "name": "The Hans India - Business",
        "url": "https://www.thehansindia.com/rss/business",
        "category": "business",
        "type": "rss",
    },
    {
        "name": "The Hans India - Cinema",
        "url": "https://www.thehansindia.com/rss/cinema",
        "category": "movies",
        "type": "rss",
    },
    {
        "name": "Deccan Chronicle",
        "url": "https://www.deccanchronicle.com/google_feeds.xml",
        "category": "breaking",
        "type": "rss",
    },
]

SOURCES = [
    source
    for source in SOURCES
    if not is_blocked_source(source.get("name"))
]


# =========================
# JUNK FILTER ONLY
# =========================
JUNK_KEYWORDS = [
    "astrology", "horoscope", "zodiac", "rashifal", "rashi phalalu",
    "recipe", "food recipe", "cooking", "kitchen", "diet", "weight loss",
    "beauty tips", "skin care", "hair care", "fashion", "relationship",
    "optical illusion", "vastu", "devotional", "temple", "puja",
    "viral photo", "viral video",
    "ఆస్ట్రాలజీ", "జ్యోతిష్యం", "రాశి ఫలాలు", "రాశిఫలాలు",
    "వంటకం", "రెసిపీ", "వంట", "ఫుడ్", "డైట్", "బరువు తగ్గడం",
    "అందం", "స్కిన్ కేర్", "హెయిర్ కేర్", "వాస్తు", "భక్తి",
]


# =========================
# DB
# =========================
def ensure_table():
    """Make sure the ``news`` table exists. Indexes are created by main.py."""
    log("Checking database table...")

    with get_cursor(commit=True) as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS news (
                id SERIAL PRIMARY KEY,
                source TEXT,
                title TEXT,
                title_original TEXT,
                link TEXT UNIQUE,
                summary TEXT,
                ai_summary TEXT,
                image TEXT,
                published TIMESTAMP DEFAULT NOW(),
                category TEXT DEFAULT 'breaking'
            );
            """
        )
        # Backfill column for older deployments that already have a `news`
        # table without `title_original`.
        cur.execute(
            "ALTER TABLE news ADD COLUMN IF NOT EXISTS title_original TEXT;"
        )
    log("Database table ready.")


def _entry_published_dt(entry) -> datetime | None:
    """Best-effort published datetime from a feedparser entry."""
    for attr in ("published_parsed", "updated_parsed", "created_parsed"):
        ts = getattr(entry, attr, None)
        if ts:
            try:
                return datetime.fromtimestamp(
                    calendar.timegm(ts), tz=timezone.utc
                )
            except (OverflowError, OSError, ValueError, TypeError):
                continue
    return None


# =========================
# HELPERS
# =========================
def fix_mojibake_text(text: str) -> str:
    if not text:
        return ""

    text = str(text)
    mojibake_markers = ["à°", "à±", "à²", "à³", "â€", "Ã", "Â"]

    if any(marker in text for marker in mojibake_markers):
        for enc in ["latin1", "cp1252"]:
            try:
                fixed = text.encode(enc, errors="ignore").decode(
                    "utf-8",
                    errors="ignore",
                )
                if fixed and fixed != text and re.search(r"[\u0C00-\u0C7F]", fixed):
                    return fixed.strip()
            except Exception:
                pass

    return text.strip()


def clean_html_text(text: str) -> str:
    if not text:
        return ""

    text = html.unescape(str(text))
    text = fix_mojibake_text(text)
    text = BeautifulSoup(text, "html.parser").get_text(" ", strip=True)
    text = fix_mojibake_text(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def clean_ai_text_preserve_lines(text: str) -> str:
    if not text:
        return ""

    text = html.unescape(str(text))
    text = fix_mojibake_text(text)
    text = BeautifulSoup(text, "html.parser").get_text("\n", strip=True)
    text = fix_mojibake_text(text)
    text = text.replace("\r", "\n")

    lines = []

    for raw_line in text.split("\n"):
        line = raw_line.strip()

        if not line:
            continue

        line = re.sub(r"^\s*[-•*]\s*", "", line)
        line = re.sub(r"^\s*\d+[\).\-\:]\s*", "", line)
        line = re.sub(r"\s+", " ", line).strip()

        if line:
            lines.append(line)

    return "\n".join(lines).strip()


def safe_translate(text: str) -> str:
    if not translator or not text or len(text.strip()) < 3:
        return text

    try:
        translated = translator.translate(text)
        return translated if translated else text
    except Exception as e:
        log(f"    [Translation Error] {e}")
        return text


def contains_any(text: str, keywords: list[str]) -> bool:
    lowered = (text or "").lower()
    return any(keyword.lower() in lowered for keyword in keywords)


def choose_final_category(title: str, text: str, source_category: str) -> str:
    """
    Final deployment-safe category rule:
    - Junk content is dropped (``cats.IGNORE_CATEGORY``).
    - Otherwise the category comes from the source config.
    - The single source of truth is ``categories.VALID_CATEGORIES``.
    """
    combined = f"{title or ''} {text or ''}".lower()

    if contains_any(combined, JUNK_KEYWORDS):
        return cats.IGNORE_CATEGORY

    return cats.normalize(source_category)


def is_duplicate_title(title: str, existing_titles: set, threshold: int = 85) -> bool:
    """Fuzzy dedup against existing titles (O(n) by nature of fuzzy comparison)."""
    title_l = title.lower().strip()

    if not title_l:
        return True

    for existing_title in existing_titles:
        existing_l = existing_title.lower().strip()

        if not existing_l:
            continue

        if fuzz.ratio(title_l, existing_l) >= threshold:
            return True

    return False


def normalize_url(url: str, base_url: str) -> str:
    if not url:
        return ""

    url = url.strip()

    if url.startswith("//"):
        parsed_base = urlparse(base_url)
        return f"{parsed_base.scheme}:{url}"

    return urljoin(base_url, url)


def is_valid_article_link(link: str, base_domain: str) -> bool:
    if not link:
        return False

    parsed = urlparse(link)

    if parsed.scheme not in {"http", "https"}:
        return False

    if not parsed.netloc:
        return False

    bad_patterns = [
        "/tag/", "/author/", "/category/", "/topics/", "/topic/",
        "/photo", "/video", "/videos", "/live-tv", "/weather",
        "/astrology", "/web-stories", "/privacy", "/contact", "/about",
        "/advertise", "facebook.com", "twitter.com", "x.com",
        "instagram.com", "youtube.com", "whatsapp",
    ]

    lower_link = link.lower()

    if any(pattern in lower_link for pattern in bad_patterns):
        return False

    return True


def is_probably_logo_image(image_url: str) -> bool:
    if not image_url:
        return True

    lower = image_url.lower()

    # SVGs are effectively always logos/icons in a news-photo context.
    if lower.split("?", 1)[0].endswith(".svg"):
        return True

    # Match only against the filename (last path segment), NOT the whole URL,
    # so a CDN directory like ".../default/..." or ".../icon/..." doesn't cause
    # a legitimate article photo to be discarded.
    path = urlparse(lower).path
    fname = path.rsplit("/", 1)[-1] or path

    logo_markers = [
        "logo", "watermark", "favicon", "sprite", "placeholder",
        "transparent", "blank", "1x1", "no-image", "noimage", "dummy",
        "avatar", "-icon", "icon-", "_icon",
    ]

    return any(marker in fname for marker in logo_markers)


def clean_image_url(image_url: str) -> str:
    if not image_url:
        return ""

    image_url = image_url.strip()

    if is_probably_logo_image(image_url):
        return ""

    return image_url


def is_bad_placeholder_summary(text: str) -> bool:
    if not text:
        return False

    lowered = text.lower().strip()

    bad_phrases = [
        "more details are being updated",
        "details are being updated",
        "story is developing",
        "this is a developing story",
        "more details awaited",
        "more details soon",
        "details awaited",
        "will be updated",
        "updates soon",
        "stay tuned",
    ]

    return any(phrase in lowered for phrase in bad_phrases)


def set_response_encoding(response):
    try:
        response.encoding = response.apparent_encoding or "utf-8"
    except Exception:
        response.encoding = "utf-8"


# =========================
# RSS SCRAPING
# =========================
def fetch_feed(feed_url: str):
    try:
        response = requests.get(
            feed_url,
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT,
        )

        set_response_encoding(response)
        response.raise_for_status()

        return feedparser.parse(response.text)

    except requests.exceptions.Timeout:
        log(f"  ✗ Feed timeout: {feed_url}")
    except requests.exceptions.RequestException as e:
        log(f"  ✗ Feed request error: {e}")
    except Exception as e:
        log(f"  ✗ Feed parse error: {e}")

    return None


def extract_image_from_entry(entry) -> str:
    try:
        if hasattr(entry, "media_content") and entry.media_content:
            url = entry.media_content[0].get("url", "").strip()
            if url:
                return clean_image_url(url)

        if hasattr(entry, "media_thumbnail") and entry.media_thumbnail:
            url = entry.media_thumbnail[0].get("url", "").strip()
            if url:
                return clean_image_url(url)

        if hasattr(entry, "links"):
            for link in entry.links:
                href = link.get("href", "").strip()
                media_type = link.get("type", "")

                if href and media_type.startswith("image/"):
                    return clean_image_url(href)

        if hasattr(entry, "enclosures") and entry.enclosures:
            for enclosure in entry.enclosures:
                href = enclosure.get("href", "").strip()
                media_type = enclosure.get("type", "")

                if href and media_type.startswith("image/"):
                    return clean_image_url(href)

        possible_html = ""

        if hasattr(entry, "summary"):
            possible_html += entry.summary or ""

        if hasattr(entry, "content") and entry.content:
            possible_html += " " + (entry.content[0].get("value", "") or "")

        if possible_html:
            soup = BeautifulSoup(possible_html, "html.parser")
            img = soup.find("img")

            if img and img.get("src"):
                return clean_image_url(img["src"].strip())

    except Exception:
        pass

    return ""


def get_entry_text(entry) -> tuple[str, str, str]:
    title = clean_html_text(getattr(entry, "title", "") or "")
    link = (getattr(entry, "link", "") or "").strip()

    description = ""

    if hasattr(entry, "summary"):
        description = entry.summary or ""
    elif hasattr(entry, "description"):
        description = entry.description or ""

    if not description and hasattr(entry, "content") and entry.content:
        description = entry.content[0].get("value", "") or ""

    description = clean_html_text(description)

    return title, link, description


def scrape_rss_source(source_config: dict) -> list[dict]:
    source_name = source_config["name"]
    feed_url = source_config["url"]
    source_category = source_config["category"]

    log(f"  Fetching RSS: {source_name}")
    log(f"  URL: {feed_url}")

    feed = fetch_feed(feed_url)

    if not feed:
        log(f"  → Skipped {source_name}")
        return []

    entries = getattr(feed, "entries", [])
    log(f"  ✓ {len(entries)} RSS entries found")

    articles = []

    for entry in entries[:MAX_ENTRIES_PER_SOURCE]:
        title, link, desc = get_entry_text(entry)

        if not title or not link:
            continue

        image = "" if SAFE_IMAGES_ONLY else extract_image_from_entry(entry)
        published_dt = _entry_published_dt(entry)

        articles.append(
            {
                "source": source_name,
                "title": title,
                "link": link,
                "description": desc,
                "image": image,
                "source_category": source_category,
                "source_type": "rss",
                "published_dt": published_dt,
            }
        )

    return articles


# =========================
# PAGE / ARTICLE EXTRACTION
# =========================
def extract_image_from_page(url: str) -> str:
    if SKIP_PAGE_IMAGE_EXTRACTION:
        return ""

    try:
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=PAGE_IMAGE_TIMEOUT,
        )

        set_response_encoding(response)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        og = soup.find("meta", property="og:image")
        if og and og.get("content"):
            return clean_image_url(normalize_url(og["content"], url))

        twitter = soup.find("meta", attrs={"name": "twitter:image"})
        if twitter and twitter.get("content"):
            return clean_image_url(normalize_url(twitter["content"], url))

        # Strip site chrome so the first <img> we grab isn't the masthead logo
        # or a nav icon; prefer an image inside the article body.
        for tag in soup(["nav", "header", "footer", "aside", "svg"]):
            tag.decompose()
        scope = soup.find("article") or soup
        img = scope.find("img")
        if img and img.get("src"):
            return clean_image_url(normalize_url(img["src"], url))

    except requests.exceptions.Timeout:
        log("    [Image Page Timeout]")
    except Exception:
        pass

    return ""


def extract_full_article_text(url: str) -> str:
    try:
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=ARTICLE_TEXT_TIMEOUT,
        )

        set_response_encoding(response)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        for tag in soup(
            [
                "script", "style", "noscript", "iframe", "svg",
                "nav", "footer", "header", "aside", "form", "button",
            ]
        ):
            tag.decompose()

        candidates = []

        article_tag = soup.find("article")
        if article_tag:
            candidates.append(article_tag)

        common_selectors = [
            "[itemprop='articleBody']",
            ".article-body", ".story-body", ".story__body",
            ".post-content", ".entry-content", ".td-post-content",
            ".content", ".main-content", ".article-content",
            ".news-content", ".story-element-text", ".full-details",
            ".articleCont", ".articlebodycontent", ".articleBody",
            ".story-content", ".post-body", ".article__body",
            ".story__content", ".newsArticle",
        ]

        for selector in common_selectors:
            selected = soup.select_one(selector)
            if selected:
                candidates.append(selected)

        if not candidates:
            candidates.append(soup.body or soup)

        best_text = ""

        junk_phrases = [
            "read more", "also read", "advertisement", "subscribe",
            "follow us", "download app", "click here", "watch video",
            "published at", "updated at", "copyright", "terms of use",
            "privacy policy", "for breaking news", "latest news",
            "join our", "whatsapp channel", "telegram channel",
            "share this article", "listen to article", "sign in", "log in",
            "recommended", "related stories", "next article", "previous article",
        ]

        for candidate in candidates:
            paragraphs = []

            for p in candidate.find_all(["p", "h2"], recursive=True):
                text = clean_html_text(p.get_text(" ", strip=True))

                if len(text) < 30:
                    continue

                if len(text.split()) < 6:
                    continue

                lower_text = text.lower()

                if any(junk in lower_text for junk in junk_phrases):
                    continue

                paragraphs.append(text)

            joined = " ".join(paragraphs)
            joined = re.sub(r"\s+", " ", joined).strip()

            if len(joined) > len(best_text):
                best_text = joined

        # Truncate at a sentence boundary to avoid feeding the AI a cut-off article.
        max_chars = 7000
        if len(best_text) > max_chars:
            truncated = best_text[:max_chars]
            last_boundary = max(
                truncated.rfind(". "),
                truncated.rfind("! "),
                truncated.rfind("? "),
            )
            if last_boundary > max_chars // 2:
                truncated = truncated[: last_boundary + 1]
            best_text = truncated
        return best_text.strip()

    except requests.exceptions.Timeout:
        log("    [Article Text Timeout]")
    except requests.exceptions.HTTPError as e:
        log(f"    [Article Text HTTP Error] {e}")
    except Exception as e:
        log(f"    [Article Text Error] {e}")

    return ""


def scrape_page_source(source_config: dict) -> list[dict]:
    source_name = source_config["name"]
    page_url = source_config["url"]
    source_category = source_config["category"]

    log(f"  Fetching PAGE: {source_name}")
    log(f"  URL: {page_url}")

    try:
        response = requests.get(
            page_url,
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT,
        )

        set_response_encoding(response)
        response.raise_for_status()

    except requests.exceptions.Timeout:
        log(f"  ✗ Page timeout: {page_url}")
        return []
    except Exception as e:
        log(f"  ✗ Page request error: {e}")
        return []

    soup = BeautifulSoup(response.text, "html.parser")

    candidates = []
    seen_links = set()
    base_domain = urlparse(page_url).netloc

    selectors = [
        "article a", "h1 a", "h2 a", "h3 a",
        ".story a", ".news a", ".article a", ".card a",
        ".entry-title a", ".post-title a", "a",
    ]

    for selector in selectors:
        for a in soup.select(selector):
            if len(candidates) >= MAX_ENTRIES_PER_SOURCE * 5:
                break

            raw_link = a.get("href", "")
            link = normalize_url(raw_link, page_url)

            if not is_valid_article_link(link, base_domain):
                continue

            if link in seen_links:
                continue

            title = clean_html_text(a.get_text(" ", strip=True))

            if len(title) < 18:
                img = a.find("img")
                if img:
                    title = clean_html_text(img.get("alt") or img.get("title") or "")

            if len(title) < 18:
                continue

            image = ""

            parent = a.find_parent(["article", "div", "li", "section"]) or a
            img = parent.find("img") if parent else None

            if img:
                image = (
                    img.get("data-src")
                    or img.get("data-lazy-src")
                    or img.get("src")
                    or ""
                )
                image = clean_image_url(normalize_url(image, page_url))

            seen_links.add(link)

            candidates.append(
                {
                    "source": source_name,
                    "title": title,
                    "link": link,
                    "description": "",
                    "image": image,
                    "source_category": source_category,
                    "source_type": "page",
                }
            )

        if len(candidates) >= MAX_ENTRIES_PER_SOURCE:
            break

    log(f"  ✓ {len(candidates)} page candidates found")

    return candidates[:MAX_ENTRIES_PER_SOURCE]


# =========================
# AI SUMMARY - IMPROVED PROMPTS & QUALITY
# =========================

_SENTENCE_END = re.compile(r"[.?!।]$")


def normalize_ai_summary(text: str) -> str:
    lines = [l.strip() for l in (text or "").split("\n") if l.strip()]
    if not lines:
        return ""
    # If the model returned one flowing paragraph instead of one sentence per
    # line, split it on sentence boundaries so the 5-8 "line" check reflects the
    # sentence count (otherwise a perfectly good paragraph is rejected as 1 line).
    if len(lines) == 1:
        parts = [p.strip() for p in re.split(r"(?<=[.?!।])\s+", lines[0]) if p.strip()]
        if len(parts) >= MIN_AI_SUMMARY_LINES:
            lines = parts
    lines = lines[:MAX_AI_SUMMARY_LINES]
    # If the last line doesn't end with sentence-ending punctuation, it may be
    # truncated — drop it only when we still have at least MIN_AI_SUMMARY_LINES
    # remaining so we never go below the required floor.
    if (
        len(lines) > MIN_AI_SUMMARY_LINES
        and not _SENTENCE_END.search(lines[-1])
    ):
        lines = lines[:-1]
    return "\n".join(lines).strip()


def ai_summary_line_count(text: str) -> int:
    return len([line for line in (text or "").split("\n") if line.strip()])



def _summary_prompt_lang() -> str:
    """All generated summaries must be Telugu-only."""
    return SUMMARY_LANGUAGE


def build_ai_prompt(title: str, article_text: str, category: str = "breaking") -> str:
    lang = SUMMARY_LANGUAGE
    script_hint = "Telugu script only"
    return f"""
You MUST rewrite the news headline and summary in Telugu only.

CRITICAL - STRICT LENGTH RULE - DO NOT VIOLATE:
The summary MUST have EXACTLY 5 to 8 lines. NO MORE. NO LESS.
Count your lines before outputting. Each line is ONE complete sentence.

FORMAT:
HEADLINE: (one short {lang} line)
SUMMARY:
line 1 of summary
line 2 of summary
...
(line 5 to line 8 max)

RULES:
- EVERY line must be in {script_hint}.
- Do NOT use English words, Latin letters, Hinglish, Hindi, or transliteration.
- The HEADLINE must also be rewritten/summarized in Telugu, not copied from the source.
- One sentence per line. No empty lines.
- Only facts from the article. No opinions.
- No bullets, numbers, headings, or extra text.

TITLE: {title}
ARTICLE: {article_text}

NOW OUTPUT. Remember: 5 to 8 lines EXACTLY.
""".strip()


def call_nvidia_summary(prompt: str, max_tokens: int = 2000, temperature: float = 0.2) -> str:
    """Call the LLM with automatic fallback across providers on rate limits.

    When finish_reason=\"length\" indicates truncation the call is retried with
    a larger token budget repeatedly until a complete response is received.
    """
    if not ai_client:
        return ""

    provider_name = AI_PROVIDER
    retries_remaining = 2  # brief retry for transient errors on same provider
    rate_limit_retries_remaining = 2  # back off & retry SAME provider before switching
    truncation_retries_remaining = 3
    lang = _summary_prompt_lang()
    lang_label = f"in {lang}" if lang == "English" else f"in {lang} (Telugu script)"

    while True:
        try:
            # Use /no_think control token only for NVIDIA Nemotron
            system_content = (
                ("/no_think\n" if AI_PROVIDER == "nvidia" else "")
                + f"You are a {lang} news editor. STRICT: Always output exactly 5-8 lines {lang_label}. "
                "Never fewer than 5. Never more than 8. Count your lines. One sentence per line."
            )

            response = ai_client.chat.completions.create(
                model=AI_MODEL,
                messages=[
                    {"role": "system", "content": system_content},
                    {"role": "user", "content": prompt},
                ],
                temperature=min(temperature, 0.2),
                top_p=0.95,
                max_tokens=max_tokens,
                stream=False,
                timeout=30,
            )

            if not response.choices:
                return ""

            choice = response.choices[0]
            if choice.finish_reason == "length" and truncation_retries_remaining > 0:
                truncation_retries_remaining -= 1
                old_limit = max_tokens
                # Cap the ceiling: a 5-8 line Telugu summary needs well under
                # 2000 tokens, and some providers 400 on very large max_tokens.
                max_tokens = min(max_tokens * 2, 8000)
                log(f"    [Retry] Output truncated at {old_limit} tokens. Retrying with {max_tokens} tokens ({truncation_retries_remaining} retries left)...")
                continue
            if choice.finish_reason == "length":
                log(f"    [WARNING] Output truncated at {max_tokens} tokens after 3 retries. Dropping incomplete last line.")
                partial = (choice.message.content or "").strip()
                lines = [ln.strip() for ln in partial.split("\n") if ln.strip()]
                if lines and not _SENTENCE_END.search(lines[-1]):
                    lines = lines[:-1]
                return "\n".join(lines).strip()
            return choice.message.content or ""

        except Exception as e:
            error_msg = str(e).lower()
            is_rate_limit = "429" in error_msg or "too many requests" in error_msg or "rate limit" in error_msg or "quota" in error_msg or "resource_exhausted" in error_msg
            is_auth_error = "404" in error_msg or "401" in error_msg or "403" in error_msg or "not found" in error_msg or "unauthorized" in error_msg or "api key" in error_msg

            # A transient rate limit shouldn't permanently burn a provider.
            # Back off and retry the SAME provider a couple of times first;
            # only switch away if it stays limited.
            if is_rate_limit and rate_limit_retries_remaining > 0:
                rate_limit_retries_remaining -= 1
                wait = 5.0 * (2 - rate_limit_retries_remaining)  # 5s then 10s
                log(f"    [Rate limit] {AI_PROVIDER} throttled. Backing off {wait:.0f}s, retrying same provider...")
                time.sleep(wait)
                continue

            if is_rate_limit or is_auth_error:
                log(f"    [Skip] {AI_PROVIDER} {'rate limited' if is_rate_limit else 'auth error'}. Trying next provider...")
                if _next_provider():
                    retries_remaining = 2
                    rate_limit_retries_remaining = 2
                    continue
                else:
                    log("    [Error] All providers exhausted.")
                    return ""
            elif retries_remaining > 0:
                retries_remaining -= 1
                log(f"    [Retry] {AI_PROVIDER} error: {e}. Retrying in 2s...")
                time.sleep(2.0)
                continue
            else:
                log(f"    [Error] {AI_PROVIDER}: {e}")
                if _next_provider():
                    retries_remaining = 2
                    rate_limit_retries_remaining = 2
                    continue
                else:
                    log("    [Error] All providers exhausted.")
                    return ""


def generate_ai_summary(title: str, article_text: str, category: str = "breaking") -> tuple[str, str]:
    """Returns (headline, summary). Returns ("", "") if AI unavailable."""
    if not _ensure_active_client():
        return "", ""

    clean_title = clean_html_text(title)
    clean_article_text = clean_html_text(article_text)

    # Use the same floor as should_generate_ai_summary()'s admission gate so we
    # never admit an article at MIN_AI_INPUT_CHARS and then silently drop it here.
    if len(clean_article_text) < MIN_AI_INPUT_CHARS:
        return "", ""

    clean_article_text = clean_article_text[:6500]
    prompt = build_ai_prompt(clean_title, clean_article_text, category)

    def parse_output(raw: str) -> tuple[str, str]:
        if not raw:
            return "", ""
        text = raw.strip()
        headline = ""
        summary_raw = text
        for marker in ("TELUGU SUMMARY:", "SUMMARY:"):
            if marker in text:
                head_part, _, tail = text.partition(marker)
                headline = head_part.replace("HEADLINE:", "").strip()
                summary_raw = tail.strip()
                break
        else:
            lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
            if lines and lines[0].upper().startswith("HEADLINE"):
                if len(lines) >= 2:
                    headline = lines[0][len("HEADLINE"):].lstrip(": ").strip()
                    summary_raw = "\n".join(lines[1:]).strip()
        if not headline:
            first, _, rest = text.partition("\n")
            if first.strip().upper().startswith("HEADLINE"):
                headline = first.strip()[len("HEADLINE"):].lstrip(": ").strip()
                summary_raw = rest.strip()
        # If the model omitted the HEADLINE:/SUMMARY: markers we intentionally
        # leave `headline` empty and keep the whole body as the summary. The
        # caller then generates a dedicated Telugu headline, so the headline is
        # never just a copy of the summary's first sentence (and the summary
        # never loses a line).
        headline = headline.replace("*", "").replace('"', "").replace("\u201c", "").replace("\u201d", "").strip()
        sum_lines = [ln for ln in summary_raw.splitlines() if ln.strip()]
        while sum_lines and sum_lines[0].strip().upper().startswith("HEADLINE"):
            sum_lines.pop(0)
        summary_raw = "\n".join(sum_lines).strip()
        return headline, summary_raw

    try:
        for attempt in range(1, 4):
            log(f"    Generating AI summary from article... attempt {attempt}/3")
            raw_content = call_nvidia_summary(prompt, max_tokens=4000, temperature=0.2)
            ai_headline, summary_raw = parse_output(raw_content)
            cleaned = normalize_ai_summary(summary_raw)
            line_count = ai_summary_line_count(cleaned)
            log(f"    AI summary line count: {line_count}")

            if line_count < MIN_AI_SUMMARY_LINES or line_count > MAX_AI_SUMMARY_LINES:
                log(f"    AI summary rejected: {line_count} lines (need {MIN_AI_SUMMARY_LINES}-{MAX_AI_SUMMARY_LINES})")
                continue

            if not is_telugu_only_text(cleaned, min_telugu_chars=20):
                log("    AI summary rejected: not Telugu-only.")
                continue

            # Resolve the headline. Spec: it must be a Telugu-only rewrite that
            # is NOT identical to the summary's first line. If the combined call
            # gave us no usable headline (or one that just echoes line 1), ask
            # the model for a dedicated Telugu headline instead.
            def _norm(s: str) -> str:
                return re.sub(r"\s+", " ", (s or "")).strip().rstrip(".!?।")

            first_line = cleaned.split("\n", 1)[0].strip()
            headline = ai_headline.strip()
            if (
                not is_telugu_only_text(headline, min_telugu_chars=4)
                or _norm(headline) == _norm(first_line)
            ):
                log("    Headline missing/duplicate — generating a dedicated Telugu headline...")
                headline = generate_ai_headline(
                    clean_title, clean_article_text, category
                ).strip()

            if not is_telugu_only_text(headline, min_telugu_chars=4):
                log("    AI headline rejected: not Telugu-only.")
                continue

            if _norm(headline) == _norm(first_line):
                log("    AI headline rejected: duplicates summary first line.")
                continue

            log(f"    AI summary result: {cleaned[:200] if cleaned else 'EMPTY'}")
            return headline, cleaned.strip()

        return "", ""

    except Exception as e:
        log(f"    [AI Summary Generation Error] {e}")
        return "", ""


# Telugu Unicode block: U+0C00..U+0C7F. We use this to decide whether a
# headline is already in Telugu script (so we don't waste an AI call
# re-translating it) or needs to be rewritten by the model.
_TELUGU_RE = re.compile(r"[\u0c00-\u0c7f]")
_LATIN_RE = re.compile(r"[A-Za-z]")


def has_telugu_script(text: str, min_chars: int = 4) -> bool:
    """Return True if `text` contains at least `min_chars` Telugu-script glyphs.

    Used to short-circuit AI headline translation when the source headline
    is already in Telugu (e.g. from native Telugu-language RSS feeds).
    """
    if not text:
        return False
    return len(_TELUGU_RE.findall(text)) >= min_chars


def is_telugu_only_text(text: str, min_telugu_chars: int = 8) -> bool:
    """Strict guard for generated display text.

    Numbers, whitespace, and punctuation are allowed, but Latin-script output
    is rejected because generated headlines/summaries must be Telugu-only.
    """
    if not text:
        return False
    telugu = len(_TELUGU_RE.findall(text))
    if telugu < min_telugu_chars:
        return False
    latin = len(_LATIN_RE.findall(text))
    # Telugu news legitimately contains English acronyms/brand names
    # (ICC, IPL, BJP, GDP, company names). Accept output as long as Telugu
    # clearly dominates; reject only Latin-heavy / transliterated text.
    return latin <= max(6, int(telugu * 0.20))


def _target_lang() -> str:
    """Language the model should generate in."""
    return SUMMARY_LANGUAGE


def build_headline_prompt(title: str, article_text: str, category: str) -> str:
    """Prompt that asks the model for ONLY a headline in the target language.

    Kept separate from the full summary prompt so we can call it cheaply
    even when the summary path is being skipped (e.g. short RSS body).
    """
    target = _target_lang()
    if target == "English":
        output_language_rule = (
            "STRICT LANGUAGE RULE: Write ONLY in English (Latin script). "
            "Do NOT use other languages."
        )
    else:
        output_language_rule = (
            f"STRICT LANGUAGE RULE: Write ONLY in fluent {target} script. "
            "Do NOT use English words, Latin characters, Devanagari, or transliteration. "
            f"Even if the article is in English/Hindi/any other language, output a proper "
            f"{target} headline."
        )
    category_guidance = ""
    if category == "sports":
        category_guidance = "Mention the sport, key players/teams, and result if relevant."
    elif category == "business":
        category_guidance = "Mention the company, sector, and the financial impact."
    elif category == "movies":
        category_guidance = "Mention the film/celebrity if known."
    elif category == "crime":
        category_guidance = "Mention the incident, place, and people involved."
    elif category == "breaking":
        category_guidance = "Focus on the event, place, and key people."

    # Trim article text so we don't blow up the prompt.
    article_excerpt = (article_text or "")[:2000]

    return f"""
You are a senior {target} news editor writing for a premium news app.

Task: Write ONE catchy, factual news headline in {target}.

Category: {category}
Guidance: {category_guidance}

RULES:
- Output ONLY the headline. No bullets, numbering, quotes, preamble, or explanation.
- Single line, max 18 words.
- {output_language_rule}
- Stay faithful to the source — don't invent facts.

ORIGINAL TITLE:
{title}

ARTICLE EXCERPT:
{article_excerpt}
""".strip()


def generate_ai_headline(
    title: str,
    article_text: str,
    category: str = "breaking",
) -> str:
    """Ask the LLM for a Telugu headline only. Returns "" on failure.

    When ENABLE_TRANSLATION is active the model generates an English headline
    and Google Translate converts it to Telugu — no Telugu guard needed.
    """
    if not _ensure_active_client():
        return ""

    clean_title = clean_html_text(title)
    clean_text = clean_html_text(article_text or "")

    if not clean_title:
        return ""

    try:
        prompt = build_headline_prompt(clean_title, clean_text, category)
        raw = call_nvidia_summary(prompt, max_tokens=500, temperature=0.3)
        headline = raw.strip()
        for marker in ("HEADLINE:", "హెడ్‌లైన్:", "शीर्षक:"):
            if marker in headline:
                headline = headline.split(marker, 1)[1].strip()
        headline = next(
            (ln.strip() for ln in headline.splitlines() if ln.strip()), ""
        )
        headline = (
            headline.replace("*", "")
            .replace('"', "")
            .replace("\u201c", "")
            .replace("\u201d", "")
            .strip()
        )
        if ENABLE_TRANSLATION and translator:
            translated = safe_translate(headline)
            if translated and translated != headline:
                headline = translated
        elif not has_telugu_script(headline, min_chars=2):
            return clean_title if has_telugu_script(clean_title) else ""
        time.sleep(2.0)
        return headline
    except Exception as e:
        log(f"    [AI Headline Error] {e}")
        return ""


def _ensure_active_client() -> bool:
    """If current ai_client is None, try to switch to a working provider."""
    global _ACTIVE_PROVIDER_IDX, ai_client, AI_PROVIDER, AI_API_KEY, AI_BASE_URL, AI_MODEL
    if ai_client is not None:
        return True
    if not _has_any_client:
        return False
    for i, p in enumerate(PROVIDERS):
        c = AI_CLIENTS.get(p["name"])
        if c is not None:
            _ACTIVE_PROVIDER_IDX = i
            AI_PROVIDER = p["name"]
            AI_API_KEY = p["api_key"]
            AI_BASE_URL = p["base_url"]
            AI_MODEL = p["model"]
            ai_client = c
            log(f"    [Provider] Activated: {p['name']} ({p['model']})")
            return True
    return False


def should_generate_ai_summary(category: str, source_text: str) -> bool:
    if not ENABLE_AI_SUMMARY:
        return False

    if not _ensure_active_client():
        return False

    if category not in AI_TARGET_CATEGORIES:
        return False

    if not source_text or len(source_text.strip()) < MIN_AI_INPUT_CHARS:
        return False

    return True


# =========================
# DB INSERT
# =========================
def insert_article(
    cur,
    source: str,
    title: str,
    link: str,
    summary: str,
    ai_summary: str | None,
    image: str,
    category: str,
    published: datetime | None = None,
    title_original: str | None = None,
) -> int:
    """Insert a row. ``ai_summary`` may be NULL — it'll be filled later.

    Returns the rowcount (1 = inserted, 0 = duplicate link).
    """
    cur.execute(
        """
        INSERT INTO news (source, title, title_original, link, summary, ai_summary, image, category, published)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, COALESCE(%s, NOW()))
        ON CONFLICT (link) DO NOTHING;
        """,
        (
            source,
            title,
            title_original,
            link,
            summary,
            ai_summary,
            image,
            category,
            published,
        ),
    )

    return cur.rowcount


# =========================
# MAIN SCRAPER
# =========================
def _scrape_source(source_config: dict) -> tuple[str, list[dict]]:
    """Run the appropriate scraper for one source. Returns (name, articles)."""
    name = source_config["name"]
    stype = source_config.get("type", "rss").lower().strip()
    try:
        if stype == "rss":
            return name, scrape_rss_source(source_config)
        if stype == "page":
            return name, scrape_page_source(source_config)
        log(f"  ✗ Unknown source type: {stype}")
        return name, []
    except Exception as exc:  # noqa: BLE001
        log(f"  ✗ Source scrape crashed: {name}: {exc}")
        return name, []


def _process_article(
    item: dict,
    existing_titles_set: set,
    counters: dict,
) -> dict | None:
    """Build the article dict we'd insert. Returns None to drop, or a dict."""
    total_seen = counters
    source = item["source"]
    title = clean_html_text(item["title"])
    link = item["link"].strip()
    desc = clean_html_text(item.get("description", ""))
    image = clean_image_url(item.get("image", ""))
    source_category = item.get("source_category", "breaking")
    published_dt = item.get("published_dt")  # datetime | None

    if not title or not link:
        log("    Skipped: missing title or link")
        return None

    if is_blocked_source(source):
        total_seen["ignored"] += 1
        log("    Skipped: blocked source/image copyright policy")
        return None

    log(f"    Title: {title[:100]}")

    if is_duplicate_title(title, existing_titles_set):
        total_seen["dup"] += 1
        log("    Skipped: duplicate title")
        return None

    if is_bad_placeholder_summary(title) or is_bad_placeholder_summary(desc):
        total_seen["placeholder"] += 1
        log("    Skipped: placeholder title/RSS summary")
        return None

    final_category = choose_final_category(
        title=title,
        text=f"{desc} {title}",
        source_category=source_category,
    )
    log(f"    Source category: {source_category}")
    log(f"    Final category: {final_category}")

    if final_category == cats.IGNORE_CATEGORY:
        total_seen["ignored"] += 1
        log("    Skipped: junk/ignored content")
        return None

    log("    Extracting full article text...")
    full_article_text = extract_full_article_text(link)
    log(f"    Full article text length: {len(full_article_text)}")

    if len(full_article_text) < MIN_FULL_ARTICLE_CHARS:
        total_seen["short_article"] += 1
        log("    Full article unavailable/too short. Falling back to RSS description.")
        full_article_text = ""  # we still save with the cleaned RSS summary

    if full_article_text and is_bad_placeholder_summary(full_article_text):
        total_seen["placeholder"] += 1
        log("    Full article is placeholder text. Falling back to RSS description.")
        full_article_text = ""

    # All sources are copyright-safe — use images directly.
    # Fall back to the TruthVortex placeholder only if no image was found at all.
    if not image:
        log("    Image not found in RSS. Checking article page...")
        image = clean_image_url(extract_image_from_page(link))
    if not image:
        log("    No image found anywhere. Using TruthVortex placeholder.")
        image = FALLBACK_NS_IMAGE
    else:
        log(f"    Image: {image[:80]}")

    final_title = title
    original_title = title  # always preserve the raw RSS title for audit/SEO

    if ENABLE_TRANSLATION and translator:
        log("    Translating title...")
        final_title = safe_translate(final_title)

    # Decide the summary now. Production requires every saved article to have
    # an AI-generated Telugu headline and 5-8 line Telugu summary.
    ai_summary = ""
    ai_source_text = full_article_text or desc
    if full_article_text:
        log("    AI input: full article text")
    elif ai_source_text:
        log("    AI input: RSS description")

    if not should_generate_ai_summary(
        category=final_category,
        source_text=ai_source_text,
    ):
        total_seen["ai_failed"] += 1
        log("    Skipped: AI summary is required but unavailable/disabled/input too short.")
        return None

    log("    Generating required Telugu AI headline and summary...")
    ai_headline, ai_summary = generate_ai_summary(
        final_title, ai_source_text, final_category
    )
    time.sleep(3.0)

    if not ai_headline or not ai_summary:
        total_seen["ai_failed"] += 1
        log("    Skipped: required Telugu AI headline/summary was not generated.")
        return None

    if len(ai_summary.strip()) < MIN_AI_SUMMARY_CHARS:
        total_seen["ai_failed"] += 1
        log("    Skipped: AI summary missing/too short.")
        return None

    if is_bad_placeholder_summary(ai_summary):
        total_seen["ai_failed"] += 1
        log("    Skipped: AI summary looks like placeholder.")
        return None

    line_count = ai_summary_line_count(ai_summary)
    if line_count < MIN_AI_SUMMARY_LINES or line_count > MAX_AI_SUMMARY_LINES:
        total_seen["ai_failed"] += 1
        log(f"    Skipped: AI summary has {line_count} lines.")
        return None

    if not is_telugu_only_text(ai_headline, min_telugu_chars=4):
        total_seen["ai_failed"] += 1
        log("    Skipped: AI headline is not Telugu-only.")
        return None

    if not is_telugu_only_text(ai_summary, min_telugu_chars=20):
        total_seen["ai_failed"] += 1
        log("    Skipped: AI summary is not Telugu-only.")
        return None

    final_title = ai_headline.strip()
    # Store the summary as ONE flowing paragraph, not line-separated points.
    # The model is prompted for one sentence per line only so the 5-8 length
    # check is reliable; here we join those sentences into a single paragraph
    # for storage and display.
    ai_summary = " ".join(
        ln.strip() for ln in ai_summary.split("\n") if ln.strip()
    )
    final_summary = ai_summary
    counters["ai_ok"] += 1
    log(f"    AI Headline generated: {final_title}")
    log(f"    Final AI summary sentences: {line_count}")

    return {
        "source": source,
        "title": final_title,
        "title_original": original_title,
        "link": link,
        "summary": final_summary,
        "ai_summary": ai_summary,
        "image": image,
        "category": final_category,
        "published": published_dt,
    }


def run_scraper():
    _reset_providers()
    log("=" * 60)
    log("TruthVortex Scraper Starting...")
    log("=" * 60)
    start_time = time.time()

    ensure_table()

    log("Loading existing titles for dedup...")
    # Dedup on the RAW source title (title_original), because the `title`
    # column stores the AI-generated Telugu headline — comparing a raw English
    # RSS title against Telugu headlines never matches, so dedup would be dead.
    with get_cursor() as cur:
        cur.execute(
            "SELECT COALESCE(title_original, title) FROM news "
            "WHERE COALESCE(title_original, title) IS NOT NULL "
            "ORDER BY published DESC LIMIT 1500;"
        )
        existing_titles_set = {row[0] for row in cur.fetchall() if row[0]}
    log(f"Existing articles loaded: {len(existing_titles_set)}")

    counters = {
        "seen": 0,
        "dup": 0,
        "ignored": 0,
        "placeholder": 0,
        "short_article": 0,
        "ai_failed": 0,
        "ai_ok": 0,
        "saved": 0,
        "saved_fallback": 0,
    }

    # ── Phase 1: fetch all sources in parallel ─────────────────
    log(f"Fetching {len(SOURCES)} sources with {MAX_CONCURRENT_SOURCES} workers...")
    raw_by_source: dict[str, list[dict]] = {}
    with ThreadPoolExecutor(max_workers=MAX_CONCURRENT_SOURCES) as ex:
        futures = {ex.submit(_scrape_source, s): s for s in SOURCES}
        for fut in as_completed(futures):
            src = futures[fut]
            try:
                name, articles = fut.result()
            except Exception as exc:  # noqa: BLE001
                log(f"  ✗ Source crashed: {src.get('name')}: {exc}")
                continue
            raw_by_source[name] = articles

    # ── Phase 2: process articles sequentially per source, but in
    # category order so logs stay readable.
    for source_config in SOURCES:
        source_category = source_config["category"]
        source_name = source_config["name"]

        log("")
        log(f"── Source Group: {source_category.upper()} ──")
        log(f"Source: {source_name}")

        raw_articles = raw_by_source.get(source_name, [])
        saved_count = 0

        for item in raw_articles:
            counters["seen"] += 1
            log("")
            try:
                article = _process_article(item, existing_titles_set, counters)
            except Exception as exc:  # noqa: BLE001
                log(f"    ✗ Process error: {exc}")
                continue

            if article is None:
                continue

            try:
                with get_cursor(commit=True) as cur:
                    rowcount = insert_article(
                        cur=cur,
                        source=article["source"],
                        title=article["title"],
                        link=article["link"],
                        summary=article["summary"],
                        ai_summary=article["ai_summary"],
                        image=article["image"],
                        category=article["category"],
                        published=article["published"],
                        title_original=article.get("title_original"),
                    )
                if rowcount > 0:
                    # Track the raw source title so in-run dedup works (the
                    # `title` field is the Telugu headline; dedup uses raw).
                    if article.get("title_original"):
                        existing_titles_set.add(article["title_original"])
                    saved_count += 1
                    counters["saved"] += 1
                    if not article["ai_summary"]:
                        counters["saved_fallback"] += 1
                    log(f"    ✓ Saved: {article['title'][:90]}")
                else:
                    log("    Not saved: link already exists")
            except Exception as exc:  # noqa: BLE001
                log(f"    ✗ DB error: {exc}")

        log("")
        log(f"  → {saved_count} new articles saved from {source_name}")

    elapsed = time.time() - start_time

    log("")
    log("=" * 60)
    log("Cycle done!")
    log(f"Total articles checked: {counters['seen']}")
    log(f"Duplicates skipped: {counters['dup']}")
    log(f"Irrelevant ignored: {counters['ignored']}")
    log(f"Placeholder skipped: {counters['placeholder']}")
    log(f"Short full article (fell back to RSS): {counters['short_article']}")
    log(f"AI failures (fell back to RSS): {counters['ai_failed']}")
    log(f"AI summaries generated: {counters['ai_ok']}")
    log(f"Total new articles saved: {counters['saved']}")
    log(f"Saved with RSS-fallback summary: {counters['saved_fallback']}")
    log(f"Total time: {elapsed:.1f} seconds")
    log("=" * 60)


if __name__ == "__main__":
    run_scraper()
