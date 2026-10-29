import { API_BASE } from "../constants";

export type AdminArticle = {
  id: number;
  source: string | null;
  title: string | null;
  title_original: string | null;
  link: string | null;
  summary: string | null;
  ai_summary: string | null;
  image: string | null;
  published: string | null;
  category: string | null;
  is_original: boolean;
  status: "published" | "draft";
  author: string | null;
  updated_at: string | null;
};

export class AdminError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}

function detailOf(body: unknown, fallback: string) {
  if (body && typeof body === "object" && "detail" in body) {
    const detail = (body as { detail: unknown }).detail;
    if (typeof detail === "string") return detail;
    // FastAPI validation errors: [{loc, msg}, ...]
    if (Array.isArray(detail)) {
      return detail
        .map((d) => {
          const field = Array.isArray(d?.loc) ? d.loc[d.loc.length - 1] : "";
          return field ? `${field}: ${d?.msg}` : String(d?.msg);
        })
        .join("; ");
    }
  }
  return fallback;
}

export async function adminFetch<T>(
  token: string,
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Authorization", `Bearer ${token}`);
  if (init.body && typeof init.body === "string") {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers,
    cache: "no-store",
  });

  if (response.status === 204) return undefined as T;

  let body: unknown = null;
  try {
    body = await response.json();
  } catch {
    // non-JSON error page
  }

  if (!response.ok) {
    throw new AdminError(detailOf(body, `Request failed (${response.status})`), response.status);
  }
  return body as T;
}

export function mediaUrl(image: string | null | undefined) {
  if (!image) return "";
  return image.startsWith("/media/") ? API_BASE + image : image;
}

export function formatDate(value: string | null) {
  if (!value) return "—";
  return new Date(value).toLocaleString("en-IN", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Asia/Kolkata",
  });
}
