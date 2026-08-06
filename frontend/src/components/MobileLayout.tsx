"use client";

import { memo } from "react";
import { ThemeToggle } from "./ThemeToggle";
import { SafeImage } from "./SafeImage";
import { todayLabel, getImage, getDirectImage } from "./utils";
import { SkeletonCards, SkeletonRows } from "./Skeleton";
import { MobileEmpty } from "./EmptyState";
import type { Article, Category, Theme } from "./types";

export const MobileLayout = memo(function MobileLayout({
  loading,
  error,
  menuOpen,
  setMenuOpen,
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
  onPullRefresh,
}: {
  loading: boolean;
  error: string;
  menuOpen: boolean;
  setMenuOpen: (value: boolean) => void;
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
  onPullRefresh?: () => void;
}) {
  return (
    <main className="min-h-screen bg-[#f7f7f7] px-4 py-5 text-[#070b13] lg:hidden">
      <div className="mx-auto max-w-[430px]">
        <MobileHeader
          menuOpen={menuOpen}
          setMenuOpen={setMenuOpen}
          mounted={mounted}
          theme={theme}
          onToggleTheme={onToggleTheme}
          onOpenSection={onOpenSection}
        />

        <MobileTicker article={tickerArticle} />

        {error ? (
          <div className="mt-4 rounded-2xl border border-red-100 bg-white p-5 text-sm font-black text-red-600 shadow-[0_8px_24px_rgba(15,23,42,0.08)]">
            Unable to load news. {error}
          </div>
        ) : null}

        <MobileBreakingCard
          article={breakingArticle}
          loading={loading}
          onOpen={(article) => onOpenArticle(article, "breaking")}
        />

        <MobileBusinessSection
          articles={businessArticles}
          loading={loading}
          onOpen={(article) => onOpenArticle(article, "business")}
          onOpenSection={() => onOpenSection("business")}
        />

        <MobileListSection
          title="Sports"
          articles={sportsArticles}
          loading={loading}
          onOpen={(article) => onOpenArticle(article, "sports")}
          onOpenSection={() => onOpenSection("sports")}
        />

        <MobileCompactSection
          title="Crime"
          article={crimeArticle}
          loading={loading}
          onOpen={(article) => onOpenArticle(article, "crime")}
          onOpenSection={() => onOpenSection("crime")}
        />

        <MobileCompactSection
          title="Movies"
          article={movieArticle}
          loading={loading}
          onOpen={(article) => onOpenArticle(article, "movies")}
          onOpenSection={() => onOpenSection("movies")}
        />

        <div className="h-8" />
      </div>
    </main>
  );
});

/* ── Mobile sub-components ── */

const MobileHeader = memo(function MobileHeader({
  menuOpen,
  setMenuOpen,
  mounted,
  theme,
  onToggleTheme,
  onOpenSection,
}: {
  menuOpen: boolean;
  setMenuOpen: (value: boolean) => void;
  mounted: boolean;
  theme: Theme;
  onToggleTheme: () => void;
  onOpenSection: (category: Category) => void;
}) {
  return (
    <header className="relative z-30 flex items-start justify-between pt-2">
      <div>
        <h1 className="text-[25px] font-black leading-none tracking-[-0.05em]">
          <span>Truth</span>
          <span className="text-red-600">Vortex</span>
        </h1>
        <p className="mt-2 text-[12px] font-semibold text-slate-500">
          {mounted ? todayLabel() : ""}
        </p>
      </div>

      <div className="flex items-center gap-2">
        <ThemeToggle theme={theme} onToggle={onToggleTheme} />

        <button
          type="button"
          onClick={() => setMenuOpen(!menuOpen)}
          className="flex h-11 w-11 items-center justify-center rounded-xl border border-slate-200 bg-[#eeeeee] text-[22px] font-black text-[#071225] shadow-[0_8px_20px_rgba(15,23,42,0.08)] active:scale-95"
          aria-label="Open menu"
        >
          ☰
        </button>
      </div>

      {menuOpen && (
        <div className="absolute right-0 top-[56px] w-[178px] rounded-xl border border-slate-100 bg-white py-2 shadow-[0_18px_45px_rgba(15,23,42,0.18)]">
          <MobileMenuItem icon="⌂" label="Home" active onClick={() => setMenuOpen(false)} />
          <MobileMenuItem icon="⚡" label="Breaking" onClick={() => onOpenSection("breaking")} />
          <MobileMenuItem icon="▥" label="Business" onClick={() => onOpenSection("business")} />
          <MobileMenuItem icon="◉" label="Sports" onClick={() => onOpenSection("sports")} />
          <MobileMenuItem icon="!" label="Crime" onClick={() => onOpenSection("crime")} />
          <MobileMenuItem icon="▣" label="Movies" onClick={() => onOpenSection("movies")} />
        </div>
      )}
    </header>
  );
});

const MobileMenuItem = memo(function MobileMenuItem({
  icon,
  label,
  active = false,
  onClick,
}: {
  icon: string;
  label: string;
  active?: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`flex w-full items-center gap-3 px-4 py-3 text-left text-[14px] font-black transition ${
        active ? "text-red-600" : "text-[#071225] hover:text-red-600"
      }`}
    >
      <span className="w-5 text-center text-[18px]">{icon}</span>
      <span>{label}</span>
    </button>
  );
});

const MobileTicker = memo(function MobileTicker({ article }: { article?: Article }) {
  return (
    <section className="mt-5 flex h-[42px] items-center gap-3 overflow-hidden rounded-xl border border-slate-100 bg-white px-3 shadow-[0_8px_24px_rgba(15,23,42,0.07)]">
      <span className="blink-dot h-2.5 w-2.5 shrink-0 rounded-full bg-red-600" />
      <p className="font-news-headline line-clamp-1 min-w-0 text-[13px] leading-[1.35] text-[#071225]">
        {article?.title || "AI summarized headlines will appear here."}
      </p>
    </section>
  );
});

const MobileBreakingCard = memo(function MobileBreakingCard({
  article,
  loading,
  onOpen,
}: {
  article?: Article;
  loading: boolean;
  onOpen: (article: Article) => void;
}) {
  return (
    <section className="mt-4 overflow-hidden rounded-2xl border border-slate-100 bg-white shadow-[0_10px_30px_rgba(15,23,42,0.10)]">
      {loading ? (
        <div className="p-3">
          <div className="h-[220px] animate-pulse rounded-xl bg-slate-100" />
          <div className="mt-4 h-5 w-3/4 animate-pulse rounded bg-slate-100" />
          <div className="mt-3 h-5 w-1/2 animate-pulse rounded bg-slate-100" />
        </div>
      ) : article ? (
        <button
          type="button"
          onClick={() => onOpen(article)}
          className="group w-full p-3 text-left"
        >
          <div className="relative h-[215px] overflow-hidden rounded-xl bg-slate-100">
            <SafeImage
              src={getImage(article)}
              fallbackSrc={getDirectImage(article)}
              className="h-full w-full object-cover transition duration-700 group-hover:scale-105"
            />
          </div>
          <div className="px-2 py-4">
            <h2 className="font-news-headline line-clamp-4 text-[28px] leading-[1.08] tracking-[-0.04em] text-[#071225]">
              {article.title}
            </h2>
          </div>
        </button>
      ) : (
        <MobileEmpty text="AI summarized breaking news will appear here." />
      )}
    </section>
  );
});

const MobileSectionHeader = memo(function MobileSectionHeader({
  title,
  onOpenSection,
}: {
  title: string;
  onOpenSection: () => void;
}) {
  return (
    <div className="mb-3 flex items-center justify-between">
      <div className="flex items-center gap-2">
        <span className="h-5 w-1 rounded-sm bg-red-600" />
        <h2 className="text-[17px] font-black uppercase tracking-[-0.02em] text-[#071225]">
          {title}
        </h2>
      </div>
      <button
        type="button"
        onClick={onOpenSection}
        className="text-[12px] font-black text-red-600"
      >
        View All →
      </button>
    </div>
  );
});

const MobileBusinessSection = memo(function MobileBusinessSection({
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
    <section className="mt-5 rounded-2xl border border-slate-100 bg-white p-3 shadow-[0_8px_24px_rgba(15,23,42,0.08)]">
      <MobileSectionHeader title="Business & Technology" onOpenSection={onOpenSection} />
      {loading ? (
        <SkeletonCards count={3} />
      ) : articles.length ? (
        <div className="grid grid-cols-3 gap-3">
          {articles.map((article) => (
            <button
              key={article.id}
              type="button"
              onClick={() => onOpen(article)}
              className="group text-left"
            >
              <div className="h-[96px] overflow-hidden rounded-lg bg-slate-100">
                <SafeImage
                  src={getImage(article)}
                  fallbackSrc={getDirectImage(article)}
                  className="h-full w-full object-cover transition duration-500 group-hover:scale-105"
                />
              </div>
              <h3 className="font-news-headline mt-2 line-clamp-4 text-[13px] leading-[1.2] text-[#071225] group-hover:text-red-600">
                {article.title}
              </h3>
            </button>
          ))}
        </div>
      ) : (
        <MobileEmpty text="AI summarized business headlines will appear here." />
      )}
    </section>
  );
});

const MobileListSection = memo(function MobileListSection({
  title,
  articles,
  loading,
  onOpen,
  onOpenSection,
}: {
  title: string;
  articles: Article[];
  loading: boolean;
  onOpen: (article: Article) => void;
  onOpenSection: () => void;
}) {
  return (
    <section className="mt-5 rounded-2xl border border-slate-100 bg-white p-3 shadow-[0_8px_24px_rgba(15,23,42,0.08)]">
      <MobileSectionHeader title={title} onOpenSection={onOpenSection} />
      {loading ? (
        <SkeletonRows count={3} />
      ) : articles.length ? (
        <div className="divide-y divide-slate-100">
          {articles.map((article) => (
            <button
              key={article.id}
              type="button"
              onClick={() => onOpen(article)}
              className="group grid w-full grid-cols-[108px_1fr] gap-3 py-3 text-left first:pt-0 last:pb-0"
            >
              <div className="h-[72px] overflow-hidden rounded-lg bg-slate-100">
                <SafeImage
                  src={getImage(article)}
                  fallbackSrc={getDirectImage(article)}
                  className="h-full w-full object-cover transition duration-500 group-hover:scale-105"
                />
              </div>
              <div className="min-w-0">
                <h3 className="font-news-headline line-clamp-3 text-[15px] leading-[1.25] text-[#071225] group-hover:text-red-600">
                  {article.title}
                </h3>
              </div>
            </button>
          ))}
        </div>
      ) : (
        <MobileEmpty text={`AI summarized ${title} headlines will appear here.`} />
      )}
    </section>
  );
});

const MobileCompactSection = memo(function MobileCompactSection({
  title,
  article,
  loading,
  onOpen,
  onOpenSection,
}: {
  title: string;
  article?: Article;
  loading: boolean;
  onOpen: (article: Article) => void;
  onOpenSection: () => void;
}) {
  return (
    <section className="mt-5 rounded-2xl border border-slate-100 bg-white p-3 shadow-[0_8px_24px_rgba(15,23,42,0.08)]">
      <MobileSectionHeader title={title} onOpenSection={onOpenSection} />
      {loading ? (
        <SkeletonRows count={1} />
      ) : article ? (
        <button
          type="button"
          onClick={() => onOpen(article)}
          className="group grid w-full grid-cols-[112px_1fr] gap-3 text-left"
        >
          <div className="h-[76px] overflow-hidden rounded-lg bg-slate-100">
<SafeImage
                  src={getImage(article)}
                  fallbackSrc={getDirectImage(article)}
                  className="h-full w-full object-cover transition duration-500 group-hover:scale-105"
                />
          </div>
          <div className="min-w-0">
            <h3 className="font-news-headline line-clamp-3 text-[15px] leading-[1.25] text-[#071225] group-hover:text-red-600">
              {article.title}
            </h3>
          </div>
        </button>
      ) : (
        <MobileEmpty text={`AI summarized ${title} article will appear here.`} />
      )}
    </section>
  );
});
