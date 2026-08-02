"use client";

import { memo } from "react";
import { CardShell, CardHeader, ImageBox } from "./CardShell";
import { SkeletonRows } from "./Skeleton";
import { EmptyText } from "./EmptyState";
import type { Article } from "./types";

export const BusinessCard = memo(function BusinessCard({
  articles,
  loading,
  onOpen,
  onOpenSection,
}: {
  articles: Article[];
  loading: boolean;
  onOpen: (article: Article) => void;
  onOpenSection: () => void;
}) {
  return (
    <CardShell className="col-start-1 row-start-1 h-full border-b border-r px-4 py-3">
      <CardHeader title="Business & Technology" onOpenSection={onOpenSection} />

      {loading ? (
        <SkeletonRows count={3} />
      ) : articles.length ? (
        <div className="grid h-[280px] grid-cols-3 gap-3">
          {articles.map((article) => (
            <button
              key={article.id}
              type="button"
              onClick={() => onOpen(article)}
              className="group grid min-w-0 grid-rows-[56%_44%] gap-3 border-r border-slate-100 pr-3 text-left last:border-r-0 last:pr-0"
            >
              <ImageBox article={article} />
              <div className="flex min-w-0 items-start overflow-hidden">
                <h3 className="font-news-headline line-clamp-4 text-[22px] leading-[1.16] tracking-[-0.02em] text-[#071225] transition group-hover:text-red-600">
                  {article.title}
                </h3>
              </div>
            </button>
          ))}
        </div>
      ) : (
        <EmptyText text="AI summarized business headlines will appear here." />
      )}
    </CardShell>
  );
});
