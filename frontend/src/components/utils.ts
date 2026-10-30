import { API_BASE, CATEGORIES, FALLBACK_IMAGE } from "./constants";
import type { Article, Category } from "./types";

export function normalizeCategory(value?: string | null): Category {
  const cat = (value || "breaking").toLowerCase().trim();

  if (cat === "finance") return "business";
  if (cat === "business & finance") return "business";
  if (cat.includes("business")) return "business";
  if (cat.includes("finance")) return "business";
  if (cat.includes("market")) return "business";
  if (cat.includes("technology")) return "business";
  if (cat.includes("tech")) return "business";

  if (cat === "entertainment") return "movies";
  if (cat === "movie") return "movies";
  if (cat.includes("film")) return "movies";
  if (cat.includes("cinema")) return "movies";
  if (cat.includes("movie")) return "movies";
  if (cat.includes("entertainment")) return "movies";

  if (cat === "sport") return "sports";
  if (cat.includes("sport")) return "sports";
  if (cat.includes("cricket")) return "sports";

  if (cat.includes("crime")) return "crime";
  if (cat.includes("police")) return "crime";

  if (cat.includes("education") || cat.includes("exam") || cat.includes("jobs")) return "education";

  if (CATEGORIES.includes(cat as Category)) return cat as Category;

  return "breaking";
}

export function isBrokenText(text?: string | null) {
  if (!text) return true;

  const value = text.trim();

  if (!value) return true;

  const brokenMarkers = ["à°", "à±", "à²", "à³", "â€", "Ã", "Â"];

  return brokenMarkers.some((marker) => value.includes(marker));
}

export function hasBadPlaceholder(text?: string | null) {
  if (!text) return true;

  const lower = text.toLowerCase().trim();

  const badPhrases = [
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
  ];

  return badPhrases.some((phrase) => lower.includes(phrase));
}

export function hasValidSummary(article: Article) {
  const text = article.body?.trim();

  if (!text) return false;
  if (text.length < 40) return false;
  if (hasBadPlaceholder(text)) return false;
  if (isBrokenText(article.title)) return false;

  return true;
}

export function getText(article?: Article | null) {
  return article?.body?.trim() || article?.summary?.trim() || "";
}

// Images uploaded in the admin newsroom are stored as "/media/<id>" on the API.
function ownMediaUrl(image: string) {
  return image.startsWith("/media/") ? API_BASE + image : null;
}

export function getImage(article?: Article | null) {
  const image = article?.image?.trim();

  if (!image || image.startsWith("data:")) return FALLBACK_IMAGE;

  // Our own uploads are already sized by the editor and served with a
  // long cache; no need to route them through the resizing proxy.
  const own = ownMediaUrl(image);
  if (own) return own;

  // Try direct image first; if it fails (CORS/blocked), fallback to wsrv
  const wsrvUrl = `https://images.weserv.nl/?url=${encodeURIComponent(image)}&w=600&output=webp&q=80`;

  // We can't easily detect failure here without loading twice, so return wsrv
  // as primary but add data-original for potential client-side fallback
  return wsrvUrl;
}

export function getDirectImage(article?: Article | null) {
  const image = article?.image?.trim();
  if (!image || image.startsWith("data:")) return FALLBACK_IMAGE;
  return ownMediaUrl(image) ?? image;
}

export function todayLabel() {
  return new Date().toLocaleDateString("en-IN", {
    weekday: "long",
    day: "2-digit",
    month: "long",
    year: "numeric",
    timeZone: "Asia/Kolkata",
  });
}

export function rotateSlice<T>(items: T[], start: number, count: number) {
  if (!items.length) return [];

  return Array.from({ length: Math.min(count, items.length) }, (_, index) => {
    return items[(start + index) % items.length];
  });
}
