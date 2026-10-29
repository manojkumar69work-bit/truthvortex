import { API_BASE } from "./constants";

export type TrackEvent = {
  kind: "pageview" | "article_view" | "source_click";
  article_id?: number;
  category?: string;
};

/** Fire-and-forget analytics beacon to the API's POST /track.
 *  Sent as text/plain so the browser skips the CORS preflight; no cookies,
 *  no identifiers — the API derives a daily, non-reversible visitor hash. */
export function track(event: TrackEvent) {
  if (typeof window === "undefined") return;

  const referrer = document.referrer;
  const external =
    referrer && !referrer.startsWith(window.location.origin) ? referrer : undefined;

  const body = JSON.stringify({
    ...event,
    path: window.location.pathname,
    referrer: event.kind === "pageview" ? external : undefined,
  });

  try {
    const url = `${API_BASE}/track`;
    if (navigator.sendBeacon) {
      navigator.sendBeacon(url, new Blob([body], { type: "text/plain" }));
    } else {
      void fetch(url, { method: "POST", body, keepalive: true }).catch(() => {});
    }
  } catch {
    // Analytics must never break the page.
  }
}
