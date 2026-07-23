import type { Metadata, Viewport } from "next";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import "./globals.css";

const siteUrl =
  process.env.NEXT_PUBLIC_SITE_URL || "https://truthvortex.example";

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title: {
    default: "TruthVortex — Live News Dashboard",
    template: "%s · TruthVortex",
  },
  description:
    "TruthVortex is a live news dashboard aggregating Breaking, Sports, Business, Movies, and Crime headlines with concise Telugu summaries.",
  applicationName: "TruthVortex",
  keywords: [
    "TruthVortex",
    "live news",
    "Telugu news",
    "breaking news",
    "Telangana news",
    "sports",
    "business",
    "movies",
    "crime",
  ],
  authors: [{ name: "TruthVortex" }],
  alternates: { canonical: "/" },
  openGraph: {
    type: "website",
    siteName: "TruthVortex",
    title: "TruthVortex — Live News Dashboard",
    description:
      "Live headlines across Breaking, Sports, Business, Movies, and Crime with concise Telugu summaries.",
    url: siteUrl,
    locale: "en_IN",
  },
  twitter: {
    card: "summary_large_image",
    title: "TruthVortex — Live News Dashboard",
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
  themeColor: "#050b1a",
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
