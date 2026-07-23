"use client";

import { useState, useEffect, memo } from "react";
import { FALLBACK_IMAGE } from "./constants";

function SafeImageComponent({ 
  src, 
  className, 
  fallbackSrc 
}: { 
  src: string; 
  className: string;
  fallbackSrc?: string;
}) {
  const [finalSrc, setFinalSrc] = useState(src || FALLBACK_IMAGE);
  const [loaded, setLoaded] = useState(false);
  const [triedFallback, setTriedFallback] = useState(false);

  useEffect(() => {
    setFinalSrc(src || FALLBACK_IMAGE);
    setLoaded(false);
    setTriedFallback(false);
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
          if (!triedFallback && fallbackSrc && fallbackSrc !== finalSrc) {
            setTriedFallback(true);
            setFinalSrc(fallbackSrc);
          } else {
            setFinalSrc(FALLBACK_IMAGE);
            setLoaded(true);
          }
        }}
      />
    </div>
  );
}

export const SafeImage = memo(SafeImageComponent);
