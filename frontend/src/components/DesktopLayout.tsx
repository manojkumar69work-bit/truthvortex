"use client";

import { memo } from "react";
import { Header } from "./Header";
import { BusinessCard } from "./BusinessCard";
import { CrimeCard } from "./CrimeCard";
import { SportsCard } from "./SportsCard";
import { BreakingCard } from "./BreakingCard";
import { MoviesCard } from "./MoviesCard";
import type { Article, Category, Theme } from "./types";

export const DesktopLayout = memo(function DesktopLayout({
  loading,
  error,
  theme,
  onToggleTheme,
  mounted,
  tickerArticle,
  breakingArticle,
  businessArticles,
  sportsArticles,
  crimeArticle,
  movieArticle,
  onOpenArticle,
  onOpenSection,
}: {
  loading: boolean;
  error: string;
  theme: Theme;
  onToggleTheme: () => void;
  mounted: boolean;
  tickerArticle?: Article;
  breakingArticle?: Article;
  businessArticles: Article[];
  sportsArticles: Article[];
  crimeArticle?: Article;
  movieArticle?: Article;
  onOpenArticle: (article: Article, section?: Category) => void;
  onOpenSection: (category: Category) => void;
}) {
  return (
    <main className="tv-desk hidden overflow-hidden bg-[#f8fafc] text-[#071225] lg:block">
      <div className="flex h-full w-full px-6 py-3">
        <section className="flex min-w-0 flex-1 flex-col">
          <Header
            mounted={mounted}
            tickerArticle={tickerArticle}
            theme={theme}
            onToggleTheme={onToggleTheme}
          />

          <section className="grid min-h-0 flex-1 grid-cols-[1.55fr_0.7fr_0.9fr] grid-rows-[minmax(220px,1.4fr)_minmax(180px,1fr)_minmax(180px,1.1fr)]">
            <BusinessCard
              articles={businessArticles}
              loading={loading}
              onOpen={(article) => onOpenArticle(article, "business")}
              onOpenSection={() => onOpenSection("business")}
            />

            <CrimeCard
              article={crimeArticle}
              loading={loading}
              onOpen={(article) => onOpenArticle(article, "crime")}
              onOpenSection={() => onOpenSection("crime")}
            />

            <SportsCard
              articles={sportsArticles}
              loading={loading}
              onOpen={(article) => onOpenArticle(article, "sports")}
              onOpenSection={() => onOpenSection("sports")}
            />

            <BreakingCard
              article={breakingArticle}
              loading={loading}
              error={error}
              onOpen={(article) => onOpenArticle(article, "breaking")}
              onOpenSection={() => onOpenSection("breaking")}
            />

            <MoviesCard
              article={movieArticle}
              loading={loading}
              onOpen={(article) => onOpenArticle(article, "movies")}
              onOpenSection={() => onOpenSection("movies")}
            />
          </section>
        </section>

        <aside className="tv-cell ml-4 hidden w-[210px] shrink-0 overflow-hidden border-l pl-4 xl:flex">
          <div className="relative flex h-full w-full flex-col items-center justify-center px-6 text-center">
            <div className="absolute left-6 top-8 h-5 w-5 rounded-full bg-orange-300" />
            <div className="absolute right-8 top-20 h-20 w-20 rounded-full border border-orange-200" />
            <div className="absolute bottom-[-70px] left-[-40px] h-56 w-56 rounded-full bg-red-300/45" />
            <div className="absolute bottom-[-40px] right-[-60px] h-52 w-52 rounded-full bg-orange-300/50" />

            <div className="relative z-10">
              <p className="text-3xl font-black leading-tight text-[#071225]">
                Space for <br /> Your Brand
              </p>
              <p className="mt-5 text-lg font-bold text-red-500">
                Advertise Here
              </p>
              <button className="mt-6 rounded-md border border-red-300 bg-white/60 px-5 py-2 text-xs font-black uppercase tracking-[0.14em] text-red-600 backdrop-blur transition hover:bg-red-600 hover:text-white">
                Know More
              </button>
            </div>
          </div>
        </aside>
      </div>
    </main>
  );
});
