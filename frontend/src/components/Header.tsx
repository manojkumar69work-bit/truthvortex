"use client";

import { memo } from "react";
import { ThemeToggle } from "./ThemeToggle";
import { todayLabel } from "./utils";
import type { Article, Theme } from "./types";

export const Header = memo(function Header({
  mounted,
  tickerArticle,
  theme,
  onToggleTheme,
}: {
  mounted: boolean;
  tickerArticle?: Article;
  theme: Theme;
  onToggleTheme: () => void;
}) {
  return (
    <header className="tv-cell grid h-[76px] shrink-0 grid-cols-[300px_1fr] border-b-[3px] border-double">
      <div className="tv-cell flex flex-col justify-center border-r pr-6">
        <h1 className="text-[34px] font-black leading-none tracking-tight text-[#071225]">
          <span>Truth</span>
          <span className="text-red-600">Vortex</span>
        </h1>
        <p className="mt-1.5 text-xs font-bold uppercase tracking-[0.16em] text-slate-500">
          {mounted ? todayLabel() : ""}
        </p>
      </div>

      <section className="flex min-w-0 items-center gap-4 overflow-hidden pl-6">
        <div className="flex shrink-0 items-center gap-2 rounded-full bg-red-600 px-3 py-1 text-[10px] font-black uppercase tracking-[0.18em] text-white">
          <span className="relative flex h-1.5 w-1.5">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-white opacity-70" />
            <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-white" />
          </span>
          Breaking
        </div>

        <p className="font-news-headline truncate text-[19px] leading-tight text-[#071225]">
          {tickerArticle?.title || "AI summarized headline will appear here after backend starts."}
        </p>

        <div className="ml-auto flex shrink-0 items-center gap-3">
          <span className="hidden text-xs font-bold text-slate-400 md:block">
            Live Updates
          </span>
          <ThemeToggle theme={theme} onToggle={onToggleTheme} />
        </div>
      </section>
    </header>
  );
});
