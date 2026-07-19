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
    <header className="grid h-[82px] shrink-0 grid-cols-[280px_1fr] gap-5">
      <div className="flex flex-col justify-center rounded-xl border border-slate-200 bg-white px-6 shadow-[0_10px_30px_rgba(15,23,42,0.06)]">
        <h1 className="text-3xl font-black leading-none tracking-tight text-[#071225]">
          <span>News</span>
          <span className="text-red-600">Sphere</span>
        </h1>
        <p className="mt-2 text-xs font-bold uppercase tracking-[0.16em] text-slate-500">
          {mounted ? todayLabel() : ""}
        </p>
      </div>

      <section className="flex min-w-0 items-center gap-4 overflow-hidden rounded-xl border border-slate-200 bg-white px-6 shadow-[0_10px_30px_rgba(15,23,42,0.06)]">
        <div className="flex shrink-0 items-center gap-2 rounded-md bg-red-600 px-4 py-2 text-xs font-black uppercase tracking-[0.16em] text-white shadow-[0_8px_20px_rgba(220,38,38,0.25)]">
          <span className="relative flex h-2.5 w-2.5">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-white opacity-70" />
            <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-white" />
          </span>
          Breaking
        </div>

        <p className="font-news-headline truncate text-[21px] leading-tight text-[#071225]">
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
