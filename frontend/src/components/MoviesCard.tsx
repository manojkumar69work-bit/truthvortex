"use client";

import { memo } from "react";
import { CardShell, CardHeader, ImageBox } from "./CardShell";
import { SkeletonRows } from "./Skeleton";
import { EmptyText } from "./EmptyState";
import type { Article } from "./types";

export const MoviesCard = memo(function MoviesCard({
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
    <CardShell className="col-start-3 row-start-3 h-full p-4">
      <CardHeader title="Movies" onOpenSection={onOpenSection} />

      {loading ? (
        <SkeletonRows count={1} />
      ) : article ? (
        <button
          type="button"
          onClick={() => onOpen(article)}
          className="group grid h-[218px] w-full grid-cols-[42%_1fr] gap-5 border-t border-slate-100 py-4 text-left"
        >
          <ImageBox article={article} />
          <div className="flex min-w-0 items-center">
            <h3 className="font-news-headline line-clamp-5 text-[23px] leading-[1.16] tracking-[-0.02em] text-[#071225] transition group-hover:text-red-600">
              {article.title}
            </h3>
          </div>
        </button>
      ) : (
        <EmptyText text="AI summarized movie article will appear here." />
      )}
    </CardShell>
  );
});
