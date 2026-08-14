import html
import logging
import os
import re

from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

# Configure module-level logger. This module is deliberately dependency-free
# with respect to scraper.py (importing it would be circular), so it owns its
# own logger instead of reusing scraper's `log()` shim.
logger = logging.getLogger("truthvortex.webutil")
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(_handler)
    logger.setLevel(os.getenv("LOG_LEVEL", "INFO").upper())
    logger.propagate = False


# =========================
# CONSTANTS
# =========================
# Telugu (and only Telugu) code block. Used to confirm that a mojibake repair
# attempt actually produced Indic text rather than more garbage.
TELUGU_RE = re.compile(r"[\u0C00-\u0C7F]")

# Byte sequences that show up when UTF-8 Telugu has been decoded as latin1/cp1252.
MOJIBAKE_MARKERS = ["à°", "à±", "à²", "à³", "â€", "Ã", "Â"]

# Matched against the *filename* only (see is_probably_logo_image).
LOGO_MARKERS = [
    "logo", "watermark", "favicon", "sprite", "placeholder",
    "transparent", "blank", "1x1", "no-image", "noimage", "dummy",
    "avatar", "-icon", "icon-", "_icon",
]

# base64 prefixes of the two classic 1x1 tracking pixels, which publishers use
# as lazy-load placeholders in <img src>.
TINY_URI_B64_PREFIXES = [
    "R0lGODlh",                                 # 1x1 GIF
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAAB",         # 1x1 PNG
]

# "1200w" / "2x" / "1.5x" srcset descriptors.
_SRCSET_DESCRIPTOR_RE = re.compile(r"^([0-9]+(?:\.[0-9]+)?)([wxh])$", re.IGNORECASE)

# Leading integer/float of an HTML dimension attribute ("1192", "1192px").
_DIMENSION_RE = re.compile(r"^\s*([0-9]+(?:\.[0-9]+)?)")

# Splits "a.jpg,https://cdn/b.jpg" without touching CDN paths like "w_100,h_100".
_SRCSET_URL_JOIN_RE = re.compile(r",(?=https?://)")


# =========================
# TEXT HELPERS
# =========================
def fix_mojibake_text(text: str) -> str:
    if not text:
        return ""

    text = str(text)

    if any(marker in text for marker in MOJIBAKE_MARKERS):
        for enc in ["latin1", "cp1252"]:
            try:
                fixed = text.encode(enc, errors="ignore").decode(
                    "utf-8",
                    errors="ignore",
                )
                if fixed and fixed != text and TELUGU_RE.search(fixed):
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


# =========================
# URL HELPERS
# =========================
def normalize_url(url: str, base_url: str) -> str:
    if not url:
        return ""

    url = url.strip()

    if url.startswith("//"):
        parsed_base = urlparse(base_url)
        return f"{parsed_base.scheme}:{url}"

    return urljoin(base_url, url)


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

    return any(marker in fname for marker in LOGO_MARKERS)


def clean_image_url(image_url: str) -> str:
    if not image_url:
        return ""

    image_url = image_url.strip()

    if is_probably_logo_image(image_url):
        return ""

    return image_url


def is_data_or_tiny_uri(url: str) -> bool:
    """True for inline data: URIs and for known 1x1 tracking-pixel payloads."""
    if not url:
        return False

    try:
        candidate = str(url).strip()

        if candidate[:5].lower() == "data:":
            return True

        return any(prefix in candidate for prefix in TINY_URI_B64_PREFIXES)
    except Exception:
        return False


# =========================
# SRCSET / DIMENSION HELPERS
# =========================
def _parse_dimension(value) -> int:
    """HTML/meta dimension -> positive int, or 0 when it is not a usable number.

    Percentages ("100%") and keywords ("auto") are deliberately unparseable:
    an unknown dimension must never be treated as a small one.
    """
    if value is None or isinstance(value, bool):
        return 0

    try:
        if isinstance(value, int):
            return value if value > 0 else 0

        if isinstance(value, float):
            return int(value) if value > 0 else 0

        text = str(value).strip()

        if not text or "%" in text:
            return 0

        match = _DIMENSION_RE.match(text)

        if not match:
            return 0

        parsed = int(float(match.group(1)))
        return parsed if parsed > 0 else 0
    except Exception:
        return 0


def _parse_srcset(srcset: str) -> list[tuple[str, float, str]]:
    """Tokenize an HTML srcset into ``(url, descriptor_value, descriptor_unit)``.

    Whitespace-token based rather than comma-split, because CDN URLs routinely
    contain commas (".../w_640,h_360/photo.jpg") that a naive split destroys.
    """
    if not srcset or not isinstance(srcset, str):
        return []

    entries: list[tuple[str, float, str]] = []
    pending_url = ""
    pending_value = 0.0
    pending_unit = ""

    def flush() -> None:
        nonlocal pending_url, pending_value, pending_unit

        if pending_url:
            entries.append((pending_url, pending_value, pending_unit))

        pending_url = ""
        pending_value = 0.0
        pending_unit = ""

    for raw_token in srcset.split():
        token = raw_token.strip()

        if not token:
            continue

        closes_candidate = token.endswith(",")
        token = token.rstrip(",").strip()

        if not token:
            flush()
            continue

        match = _SRCSET_DESCRIPTOR_RE.match(token)

        if match:
            if pending_url:
                pending_value = float(match.group(1))
                pending_unit = match.group(2).lower()
            # A descriptor with no URL in front of it is garbage; drop it.
        else:
            if pending_url:
                flush()

            parts = _SRCSET_URL_JOIN_RE.split(token)

            for part in parts[:-1]:
                if part:
                    entries.append((part, 0.0, ""))

            pending_url = parts[-1]

        if closes_candidate:
            flush()

    flush()

    return entries


def pick_srcset_largest(srcset: str) -> str:
    """Largest-w URL from a srcset, else largest-x, else the first URL."""
    try:
        entries = _parse_srcset(srcset)

        if not entries:
            return ""

        widths = [entry for entry in entries if entry[2] == "w" and entry[1] > 0]

        if widths:
            return max(widths, key=lambda entry: entry[1])[0]

        densities = [entry for entry in entries if entry[2] == "x" and entry[1] > 0]

        if densities:
            return max(densities, key=lambda entry: entry[1])[0]

        return entries[0][0]
    except Exception:
        logger.debug("pick_srcset_largest failed", exc_info=True)
        return ""


def srcset_max_width(srcset: str) -> int:
    """Largest w descriptor in a srcset, or 0 when none is parseable."""
    try:
        widths = [
            int(entry[1])
            for entry in _parse_srcset(srcset)
            if entry[2] == "w" and entry[1] > 0
        ]

        return max(widths) if widths else 0
    except Exception:
        logger.debug("srcset_max_width failed", exc_info=True)
        return 0


def is_tiny_image(width, height, *, min_w: int = 300, min_h: int = 200) -> bool:
    """True only when a dimension is *known* and below the threshold.

    ``width``/``height`` arrive as HTML attributes or og: meta strings, so they
    may be str, int or None. Missing, zero or unparseable values mean "unknown",
    and unknown is never tiny.
    """
    try:
        parsed_width = _parse_dimension(width)
        parsed_height = _parse_dimension(height)

        if parsed_width > 0 and parsed_width < min_w:
            return True

        if parsed_height > 0 and parsed_height < min_h:
            return True

        return False
    except Exception:
        logger.debug("is_tiny_image failed", exc_info=True)
        return False


# =========================
# RESPONSE HELPERS
# =========================
def set_response_encoding(response):
    try:
        response.encoding = response.apparent_encoding or "utf-8"
    except Exception:
        response.encoding = "utf-8"
