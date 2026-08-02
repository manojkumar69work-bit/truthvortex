"use client";

import { memo } from "react";
import { CardShell, CardHeader, ImageBox } from "./CardShell";
import { SkeletonRows } from "./Skeleton";
import { EmptyText } from "./EmptyState";
import type { Article } from "./types";

export const SportsCard = memo(function SportsCard({
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
    <CardShell className="col-start-3 row-span-2 row-start-1 h-full border-b px-4 py-3">
      <CardHeader title="Sports" onOpenSection={onOpenSection} />

      {loading ? (
        <SkeletonRows count={4} />
      ) : articles.length ? (
        <div className="h-[calc(100%-42px)] divide-y divide-slate-100">
          {articles.map((article) => (
            <button
              key={article.id}
              type="button"
              onClick={() => onOpen(article)}
              className="group grid h-1/4 w-full grid-cols-[42%_1fr] gap-5 py-3 text-left"
            >
              <ImageBox article={article} />
              <div className="flex min-w-0 items-center">
                <h3 className="font-news-headline line-clamp-4 text-[23px] leading-[1.16] tracking-[-0.02em] text-[#071225] transition group-hover:text-red-600">
                  {article.title}
                </h3>
              </div>
            </button>
          ))}
        </div>
      ) : (
        <EmptyText text="AI summarized sports headlines will appear here." />
      )}
    </CardShell>
  );
});
