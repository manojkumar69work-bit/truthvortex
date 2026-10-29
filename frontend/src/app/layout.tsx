import type { Metadata, Viewport } from "next";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import "./globals.css";

const siteUrl =
  process.env.NEXT_PUBLIC_SITE_URL || "https://red4ce.example";

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title: {
    default: "Red4ce — Live News Dashboard",
    template: "%s · Red4ce",
  },
  description:
    "Red4ce is a live news dashboard aggregating Breaking, Sports, Business, Movies, and Crime headlines with concise Telugu summaries.",
  applicationName: "Red4ce",
  keywords: [
    "Red4ce",
    "live news",
    "Telugu news",
    "breaking news",
    "Telangana news",
    "sports",
    "business",
    "movies",
    "crime",
  ],
  authors: [{ name: "Red4ce" }],
  alternates: { canonical: "/" },
  openGraph: {
    type: "website",
    siteName: "Red4ce",
    title: "Red4ce — Live News Dashboard",
    description:
      "Live headlines across Breaking, Sports, Business, Movies, and Crime with concise Telugu summaries.",
    url: siteUrl,
    locale: "en_IN",
  },
  twitter: {
    card: "summary_large_image",
    title: "Red4ce — Live News Dashboard",
    description:
      "Live headlines across Breaking, Sports, Business, Movies, and Crime with concise Telugu summaries.",
  },
  robots: {
    index: true,
    follow: true,
    googleBot: { index: true, follow: true },
  },
};

export const viewport: Viewport = {
  themeColor: "#ffffff",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <ErrorBoundary>{children}</ErrorBoundary>
      </body>
    </html>
  );
}
