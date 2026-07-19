"use client";

import { useState, useEffect, memo, useCallback } from "react";
import { SafeImage } from "./SafeImage";
import { getImage, getText } from "./utils";
import { LABELS } from "./constants";
import type { ActiveArticle } from "./types";

export const ArticleModal = memo(function ArticleModal({
  active,
  total,
  onClose,
  onPrev,
  onNext,
}: {
  active: ActiveArticle;
  total: number;
  onClose: () => void;
  onPrev: () => void;
  onNext: () => void;
}) {
  const { article, section, index } = active;

  const [touchStart, setTouchStart] = useState<number | null>(null);
  const [shared, setShared] = useState(false);

  const handleKey = useCallback(
    (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
      if (event.key === "ArrowRight") onNext();
      if (event.key === "ArrowLeft") onPrev();
    },
    [onClose, onNext, onPrev],
  );

  useEffect(() => {
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [handleKey]);

  async function handleShare() {
    const summary = getText(article);
    const url = typeof window !== "undefined" ? window.location.href : "";
    const shareText = summary ? `${article.title}\n\n${summary}` : article.title;

    try {
      if (typeof navigator !== "undefined" && navigator.share) {
        await navigator.share({ title: article.title, text: shareText, url });
        return;
      }

      if (typeof navigator !== "undefined" && navigator.clipboard) {
        await navigator.clipboard.writeText(`${shareText}\n${url}`.trim());
        setShared(true);
        window.setTimeout(() => setShared(false), 2000);
      }
    } catch (shareError) {
      void shareError;
    }
  }

  function handleTouchEnd() {
    if (touchStart === null) return;

    const distance = touchStart - (touchStart - 1); // reset
    // Use a ref-based approach instead
  }

  return (
    <div
      className="fixed inset-0 z-50 flex animate-fadeIn items-center justify-center bg-slate-950/60 p-0 backdrop-blur-sm sm:p-4"
      onClick={onClose}
    >
      <article
        role="dialog"
        aria-modal="true"
        aria-label={article.title}
        className="flex h-full w-full animate-slideUp flex-col overflow-hidden bg-white shadow-[0_25px_80px_rgba(15,23,42,0.25)] sm:max-h-[90vh] sm:max-w-3xl sm:rounded-xl sm:border sm:border-slate-200"
        onClick={(event) => event.stopPropagation()}
        onTouchStart={(event) => setTouchStart(event.targetTouches[0].clientX)}
        onTouchMove={(event) => {
          const currentX = event.targetTouches[0].clientX;
          if (touchStart !== null) {
            const diff = touchStart - currentX;
            if (diff > 60) {
              onNext();
              setTouchStart(null);
            } else if (diff < -60) {
              onPrev();
              setTouchStart(null);
            }
          }
        }}
        onTouchEnd={() => setTouchStart(null)}
      >
        <div className="flex items-center justify-between border-b border-slate-100 bg-white px-4 py-3">
          <div>
            <p className="text-[11px] font-black uppercase tracking-[0.22em] text-red-600">
              {LABELS[section]}
            </p>
            <p className="mt-1 text-xs font-bold text-slate-400">
              {total > 1 ? `${index + 1} / ${total}` : ""}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-md bg-[#071225] px-4 py-2 text-sm font-black text-white shadow-sm transition hover:bg-red-600"
          >
            Close
          </button>
        </div>

        <div className="hide-scrollbar flex-1 overflow-y-auto">
          <div className="flex max-h-[42vh] min-h-[260px] w-full items-center justify-center bg-slate-100 sm:max-h-[48vh]">
            <SafeImage
              src={getImage(article)}
              className="max-h-[42vh] w-full object-contain sm:max-h-[48vh]"
            />
          </div>

          <div className="p-5 sm:p-7">
            <div className="mb-4 flex flex-wrap items-center gap-3 text-xs font-black uppercase tracking-[0.2em] text-slate-400">
              <span>{article.source || "TruthVortex"}</span>
            </div>

            <h2 className="font-news-headline text-[30px] leading-[1.12] tracking-[-0.03em] text-[#071225] sm:text-4xl sm:leading-tight">
              {article.title}
            </h2>

            <div className="mt-6 rounded-lg border border-slate-200 bg-slate-50 p-5">
              <p className="font-news-summary whitespace-normal text-[17px] leading-8 text-slate-700 sm:text-lg sm:leading-9">
                {getText(article)}
              </p>
            </div>

            <button
              type="button"
              onClick={handleShare}
              className="mt-5 inline-flex items-center gap-2 rounded-md bg-[#071225] px-5 py-3 text-xs font-black uppercase tracking-[0.16em] text-white transition hover:bg-red-600"
            >
              {shared ? "Link copied ✓" : "Share ↗"}
            </button>
          </div>
        </div>

        <div className="grid grid-cols-2 border-t border-slate-100 bg-white">
          <button
            type="button"
            onClick={onPrev}
            className="border-r border-slate-100 py-4 text-sm font-black uppercase tracking-[0.16em] text-[#071225] transition hover:bg-slate-50 hover:text-red-600"
          >
            Previous
          </button>
          <button
            type="button"
            onClick={onNext}
            className="py-4 text-sm font-black uppercase tracking-[0.16em] text-[#071225] transition hover:bg-slate-50 hover:text-red-600"
          >
            Next
          </button>
        </div>
      </article>
    </div>
  );
});
