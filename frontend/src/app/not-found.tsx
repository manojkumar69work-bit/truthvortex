import Link from "next/link";
import type { CSSProperties } from "react";

export const metadata = {
  title: "Page not found",
  description: "The page you are looking for could not be found on TruthVortex.",
};

const mainStyle: CSSProperties = {
  minHeight: "100vh",
  display: "flex",
  flexDirection: "column",
  alignItems: "center",
  justifyContent: "center",
  gap: "18px",
  padding: "32px",
  textAlign: "center",
  background: "#f8fafc",
  color: "#070b13",
  fontFamily: "Arial, Helvetica, sans-serif",
};

const badgeStyle: CSSProperties = {
  width: "72px",
  height: "72px",
  borderRadius: "18px",
  background: "#050b1a",
  color: "#ffffff",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  fontSize: "30px",
  fontWeight: 900,
  letterSpacing: "1px",
};

const headingStyle: CSSProperties = {
  fontSize: "28px",
  fontWeight: 900,
  margin: 0,
};

const textStyle: CSSProperties = {
  maxWidth: "460px",
  fontSize: "15px",
  lineHeight: 1.6,
  color: "#475569",
  margin: 0,
};

const linkStyle: CSSProperties = {
  marginTop: "6px",
  padding: "12px 22px",
  borderRadius: "999px",
  background: "#050b1a",
  color: "#ffffff",
  fontWeight: 800,
  fontSize: "14px",
  textDecoration: "none",
};

export default function NotFound() {
  return (
    <main style={mainStyle}>
      <div aria-hidden="true" style={badgeStyle}>
        NS
      </div>
      <h1 style={headingStyle}>404 — Page not found</h1>
      <p style={textStyle}>
        The page you are looking for doesn&apos;t exist or may have moved. Head
        back to the live news dashboard.
      </p>
      <Link href="/" style={linkStyle}>
        Back to TruthVortex
      </Link>
    </main>
  );
}
