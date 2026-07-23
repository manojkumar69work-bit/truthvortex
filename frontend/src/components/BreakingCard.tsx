import { memo } from "react";
import { CardShell } from "./CardShell";
import { SafeImage } from "./SafeImage";
import { getImage, getDirectImage, getText } from "./utils";
import type { Article } from "./types";

export const BreakingCard = memo(function BreakingCard({
  article,
  loading,
  error,
  onOpen,
  onOpenSection,
}: {
  article?: Article;
  loading: boolean;
  error: string;
  onOpen: (article: Article) => void;
  onOpenSection: () => void;
}) {
  return (
    <CardShell className="relative col-span-2 col-start-1 row-span-2 row-start-2 h-full border-red-100 bg-gradient-to-br from-white via-[#fffafa] to-[#fff1f2]">
      <div className="absolute right-5 top-5 z-20">
        <button
          type="button"
          onClick={(event) => {
            event.stopPropagation();
            onOpenSection();
          }}
          className="rounded-md bg-white/90 px-4 py-2 text-[11px] font-black uppercase tracking-[0.12em] text-red-600 shadow-sm backdrop-blur transition hover:bg-red-600 hover:text-white"
        >
          View All →
        </button>
      </div>

      {loading ? (
        <div className="h-full p-5">
          <div className="h-full animate-pulse rounded-lg bg-slate-100" />
        </div>
      ) : error ? (
        <div className="flex h-full items-center justify-center p-8 text-center">
          <p className="text-lg font-black text-red-600">{error}</p>
        </div>
      ) : article ? (
        <button
          type="button"
          onClick={() => onOpen(article)}
          className="group grid h-full w-full grid-cols-2 overflow-hidden p-5 text-left"
        >
          <div className="relative h-full w-full overflow-hidden rounded-lg bg-slate-200 shadow-[0_12px_30px_rgba(15,23,42,0.12)]">
            <SafeImage
              src={getImage(article)}
              fallbackSrc={getDirectImage(article)}
              className="h-full w-full object-cover transition duration-700 group-hover:scale-105"
            />
            <div className="absolute inset-0 bg-gradient-to-t from-black/35 via-transparent to-transparent" />
            <div className="absolute left-5 top-5 rounded-md bg-red-600 px-4 py-2 text-xs font-black uppercase tracking-[0.2em] text-white shadow-lg">
              Breaking News
            </div>
          </div>

          <div className="flex min-w-0 flex-col justify-center px-7 text-[#071225]">
            <h2 className="font-news-headline line-clamp-4 text-[36px] leading-[1.08] tracking-[-0.02em] text-[#071225] transition group-hover:text-red-600">
              {article.title}
            </h2>
            <p className="font-news-summary mt-4 line-clamp-6 whitespace-normal text-[18px] leading-8 text-slate-600">
              {getText(article)}
            </p>
            <div className="mt-6">
              <span className="inline-flex rounded-md bg-red-600 px-5 py-3 text-xs font-black uppercase tracking-[0.16em] text-white shadow-[0_10px_25px_rgba(220,38,38,0.22)] transition group-hover:bg-[#071225]">
                Read Story →
              </span>
            </div>
          </div>
        </button>
      ) : (
        <div className="flex h-full items-center justify-center p-8 text-center">
          <p className="text-lg font-black text-slate-400">AI summarized breaking news will appear here.</p>
        </div>
      )}
    </CardShell>
  );
});
