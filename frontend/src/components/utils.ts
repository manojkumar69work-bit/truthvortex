import { CATEGORIES, FALLBACK_IMAGE } from "./constants";
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

export function hasValidAiSummary(article: Article) {
  const text = article.ai_summary?.trim();

  if (!text) return false;
  if (text.length < 40) return false;
  if (hasBadPlaceholder(text)) return false;
  if (isBrokenText(article.title)) return false;

  return true;
}

export function getText(article?: Article | null) {
  return article?.ai_summary?.trim() || article?.summary?.trim() || "";
}

export function getImage(article?: Article | null) {
  const image = article?.image?.trim();

  if (!image || image.startsWith("data:")) return FALLBACK_IMAGE;

  return `https://images.weserv.nl/?url=${encodeURIComponent(image)}&w=600&output=webp&q=80`;
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
