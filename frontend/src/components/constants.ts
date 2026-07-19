export const API_URL = (process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000") + "/news";

export const REFRESH_MS = 60000;
export const TICKER_MS = 6000;
export const SECTION_ROTATE_MS = 30000;
export const BREAKING_MS = 30000;

export const CATEGORIES = ["breaking", "business", "sports", "crime", "movies"] as const;

export const LABELS: Record<string, string> = {
  breaking: "Breaking",
  business: "Business",
  sports: "Sports",
  crime: "Crime",
  movies: "Movies",
};

export const FALLBACK_IMAGE =
  "data:image/svg+xml;charset=UTF-8,%3Csvg xmlns='http://www.w3.org/2000/svg' width='1200' height='700' viewBox='0 0 1200 700'%3E%3Crect width='1200' height='700' fill='%23050b1a'/%3E%3Crect x='36' y='36' width='1128' height='628' fill='%23071122' stroke='%231e293b' stroke-width='4'/%3E%3Ctext x='50%25' y='46%25' dominant-baseline='middle' text-anchor='middle' font-family='Arial, Helvetica, sans-serif' font-size='156' font-weight='900' fill='white'%3ETV%3C/text%3E%3Ctext x='50%25' y='61%25' dominant-baseline='middle' text-anchor='middle' font-family='Arial, Helvetica, sans-serif' font-size='42' font-weight='700' fill='%2394a3b8'%3ETruthVortex%3C/text%3E%3C/svg%3E";
