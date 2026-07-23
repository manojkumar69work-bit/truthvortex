"use client";

import { useEffect, memo, useCallback } from "react";
import { SafeImage } from "./SafeImage";
import { getImage, getDirectImage, hasValidAiSummary } from "./utils";
import { LABELS } from "./constants";
import type { Article, Category } from "./types";

export const SectionModal = memo(function SectionModal({
  category,
  articles,
  onClose,
  onOpenArticle,
}: {
  category: Category;
  articles: Article[];
  onClose: () => void;
  onOpenArticle: (article: Article) => void;
}) {
  const visibleArticles = articles.filter(hasValidAiSummary).slice(0, 9);

  const handleKey = useCallback(
    (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    },
    [onClose],
  );

  useEffect(() => {
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [handleKey]);

  return (
    <div
      className="fixed inset-0 z-40 flex animate-fadeIn items-center justify-center bg-slate-950/60 p-4 backdrop-blur-sm"
      onClick={onClose}
    >
      <section
        role="dialog"
        aria-modal="true"
        aria-label={LABELS[category]}
        className="h-[92vh] w-full max-w-7xl animate-slideUp overflow-hidden rounded-2xl border border-slate-200 bg-white p-4 shadow-[0_25px_80px_rgba(15,23,42,0.25)] sm:p-6"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="mb-5 flex items-center justify-between">
          <div>
            <p className="text-xs font-black uppercase tracking-[0.25em] text-red-600">Section</p>
            <h2 className="text-3xl font-black tracking-[-0.04em] text-[#071225] sm:text-4xl">
              {LABELS[category]}
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-md bg-[#071225] px-4 py-2.5 text-sm font-black text-white transition hover:bg-red-600 sm:px-5 sm:py-3"
          >
            Close
          </button>
        </div>

        {visibleArticles.length ? (
          <div className="hide-scrollbar grid h-[calc(100%-88px)] grid-cols-1 gap-4 overflow-y-auto sm:grid-cols-2 lg:grid-cols-3 lg:grid-rows-3">
            {visibleArticles.map((article) => (
              <button
                key={article.id}
                type="button"
                onClick={() => onOpenArticle(article)}
                className="group grid min-h-[230px] grid-rows-[55%_45%] overflow-hidden rounded-lg border border-slate-100 bg-slate-50 p-3 text-left transition hover:-translate-y-1 hover:border-slate-200 hover:bg-white hover:shadow-lg"
              >
                <div className="overflow-hidden rounded-md bg-slate-100">
                  <SafeImage
                    src={getImage(article)}
                    fallbackSrc={getDirectImage(article)}
                    className="h-full w-full object-cover transition duration-500 group-hover:scale-105"
                  />
                </div>
                <div className="flex min-h-0 flex-col justify-center overflow-hidden px-1">
                  <h3 className="font-news-headline line-clamp-5 text-[20px] leading-[1.12] tracking-[-0.02em] text-[#071225] transition group-hover:text-red-600 sm:text-[22px]">
                    {article.title}
                  </h3>
                </div>
              </button>
            ))}
          </div>
        ) : (
          <div className="flex h-[calc(100%-88px)] items-center justify-center rounded-md bg-slate-50 text-center text-lg font-black text-slate-400">
            No AI summarized articles found in this section.
          </div>
        )}
      </section>
    </div>
  );
});
