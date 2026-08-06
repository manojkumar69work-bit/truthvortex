"use client";

import { memo } from "react";
import { CardShell, CardHeader, ImageBox } from "./CardShell";
import { SkeletonRows } from "./Skeleton";
import { EmptyText } from "./EmptyState";
import type { Article } from "./types";

export const CrimeCard = memo(function CrimeCard({
  article,
  loading,
  onOpen,
  onOpenSection,
}: {
  article?: Article;
  loading: boolean;
  onOpen: (article: Article) => void;
  onOpenSection: () => void;
}) {
  return (
    <CardShell className="col-start-2 row-start-1 h-full border-b border-r px-4 py-3">
      <CardHeader title="Crime" onOpenSection={onOpenSection} />

      {loading ? (
        <SkeletonRows count={1} />
      ) : article ? (
        <button
          type="button"
          onClick={() => onOpen(article)}
          className="group grid h-[280px] w-full grid-rows-[58%_42%] gap-3 text-left"
        >
          <ImageBox article={article} />
          <div className="flex min-w-0 items-start overflow-hidden">
            <h3 className="font-news-headline line-clamp-4 text-[21px] leading-[1.22] tracking-[-0.02em] text-[#071225] transition group-hover:text-red-600">
              {article.title}
            </h3>
          </div>
        </button>
      ) : (
        <EmptyText text="AI summarized crime article will appear here." />
      )}
    </CardShell>
  );
});
