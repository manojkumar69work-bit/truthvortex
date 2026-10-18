"use client";

import { useEffect, useState } from "react";

// Matches the end of tvIntroLift in globals.css (2.15s delay + 0.5s).
const INTRO_MS = 2650;

/** TV-style opening ident, played on every page load. The markup is
 *  server-rendered so it covers the dashboard from the first paint. CSS hides
 *  it for visitors who prefer reduced motion; a click or any key skips it. */
export function TvIntro() {
  const [done, setDone] = useState(false);

  useEffect(() => {
    const skip = () => setDone(true);
    const timer = window.setTimeout(skip, INTRO_MS);
    window.addEventListener("keydown", skip);
    return () => {
      window.clearTimeout(timer);
      window.removeEventListener("keydown", skip);
    };
  }, []);

  if (done) return null;

  return (
    <div className="tv-intro" aria-hidden="true" onClick={() => setDone(true)}>
      <div className="tv-intro__screen" />
      <div className="tv-intro__brand">
        <span className="tv-intro__word tv-intro__word--left">Truth</span>
        <span className="tv-intro__word tv-intro__word--right">Vortex</span>
      </div>
      <div className="tv-intro__bar">
        <span className="tv-intro__live">
          <span className="tv-intro__dot" />
          LIVE
        </span>
        <span className="tv-intro__tagline">తెలుగు వార్తలు</span>
      </div>
    </div>
  );
}
