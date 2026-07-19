"use client";

import { useState, useEffect, memo } from "react";
import { FALLBACK_IMAGE } from "./constants";

function SafeImageComponent({ src, className }: { src: string; className: string }) {
  const [finalSrc, setFinalSrc] = useState(src || FALLBACK_IMAGE);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    setFinalSrc(src || FALLBACK_IMAGE);
    setLoaded(false);
  }, [src]);

  return (
    <div className={`relative overflow-hidden ${className}`}>
      {!loaded && (
        <div className="absolute inset-0 animate-pulse bg-slate-200" />
      )}
      <img
        src={finalSrc}
        alt=""
        loading="lazy"
        decoding="async"
        className={`h-full w-full object-cover transition-opacity duration-500 ${loaded ? "opacity-100" : "opacity-0"}`}
        onLoad={() => setLoaded(true)}
        onError={() => {
          setFinalSrc(FALLBACK_IMAGE);
          setLoaded(true);
        }}
      />
    </div>
  );
}

export const SafeImage = memo(SafeImageComponent);
