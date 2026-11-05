import type { NextRequest } from "next/server";
import { REFERER_LOCKED_IMAGE_HOSTS } from "@/components/constants";

// Only hosts listed in REFERER_LOCKED_IMAGE_HOSTS are fetched, so this can't
// be used as an open proxy.
export async function GET(request: NextRequest) {
  let url: URL;
  try {
    url = new URL(request.nextUrl.searchParams.get("url") ?? "");
  } catch {
    return new Response("Bad url", { status: 400 });
  }

  const referer = url.protocol === "https:" ? REFERER_LOCKED_IMAGE_HOSTS[url.hostname] : undefined;
  if (!referer) return new Response("Host not allowed", { status: 400 });

  let upstream: Response;
  try {
    upstream = await fetch(url, {
      headers: {
        Referer: referer,
        "User-Agent": "Mozilla/5.0 (compatible; Red4ce/1.0; +https://red4ce.com)",
      },
      // A redirect could point anywhere; refuse rather than follow it.
      redirect: "manual",
      cache: "no-store",
      signal: AbortSignal.timeout(10000),
    });
  } catch {
    return new Response("Upstream unreachable", { status: 502 });
  }

  const contentType = upstream.headers.get("content-type") ?? "";
  if (!upstream.ok || !contentType.startsWith("image/")) {
    return new Response("Upstream refused", { status: 502 });
  }

  return new Response(upstream.body, {
    headers: {
      "Content-Type": contentType,
      // Let Vercel's CDN keep each image for a day so the function runs once per image.
      "Cache-Control": "public, max-age=86400, s-maxage=86400, stale-while-revalidate=604800",
    },
  });
}
