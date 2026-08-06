"use client";

import { useState, useEffect, useMemo, useCallback } from "react";
import {
  CATEGORIES,
  LABELS,
  FALLBACK_IMAGE,
  TICKER_MS,
  BREAKING_MS,
  SECTION_ROTATE_MS,
} from "@/components/constants";
import {
  normalizeCategory,
  hasValidAiSummary,
  getText,
  rotateSlice,
} from "@/components/utils";
import { useNews } from "@/components/useNews";
import { MobileLayout } from "@/components/MobileLayout";
import { DesktopLayout } from "@/components/DesktopLayout";
import { SectionModal } from "@/components/SectionModal";
import { ArticleModal } from "@/components/ArticleModal";
import type { Category, ActiveArticle } from "@/components/types";

export default function Home() {
  const {
    articles,
    loading,
    error,
    grouped,
    breakingArticles,
    businessArticles,
    sportsArticles,
    crimeArticles,
    moviesArticles,
    articlesForSection,
    refetch,
  } = useNews();

  const [mounted, setMounted] = useState(false);
  const [theme, setTheme] = useState<"light" | "dark">("light");

  const [breakingIndex, setBreakingIndex] = useState(0);
  const [tickerIndex, setTickerIndex] = useState(0);
  const [businessIndex, setBusinessIndex] = useState(0);
  const [sportsIndex, setSportsIndex] = useState(0);
  const [crimeIndex, setCrimeIndex] = useState(0);
  const [moviesIndex, setMoviesIndex] = useState(0);

  const [menuOpen, setMenuOpen] = useState(false);
  const [selectedSection, setSelectedSection] = useState<Category | null>(null);
  const [activeArticle, setActiveArticle] = useState<ActiveArticle | null>(null);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    try {
      const stored = window.localStorage.getItem("tv-theme");
      if (stored === "dark" || stored === "light") {
        setTheme(stored);
      } else if (
        window.matchMedia &&
        window.matchMedia("(prefers-color-scheme: dark)").matches
      ) {
        setTheme("dark");
      }
    } catch {
      // localStorage not available
    }
  }, []);

  useEffect(() => {
    try {
      window.localStorage.setItem("tv-theme", theme);
    } catch {
      // localStorage not available
    }
  }, [theme]);

  const toggleTheme = useCallback(() => {
    setTheme((value) => (value === "dark" ? "light" : "dark"));
  }, []);

  // ── Rotation intervals ──
  useEffect(() => {
    if (breakingArticles.length <= 1) return;
    const interval = window.setInterval(
      () => setTickerIndex((i) => (i + 1) % breakingArticles.length),
      TICKER_MS,
    );
    return () => window.clearInterval(interval);
  }, [breakingArticles.length]);

  useEffect(() => {
    if (breakingArticles.length <= 1) return;
    const interval = window.setInterval(
      () => setBreakingIndex((i) => (i + 1) % breakingArticles.length),
      BREAKING_MS,
    );
    return () => window.clearInterval(interval);
  }, [breakingArticles.length]);

  useEffect(() => {
    const interval = window.setInterval(() => {
      setBusinessIndex((i) => (i + 3) % Math.max(businessArticles.length, 1));
      setSportsIndex((i) => (i + 4) % Math.max(sportsArticles.length, 1));
      setCrimeIndex((i) => (i + 1) % Math.max(crimeArticles.length, 1));
      setMoviesIndex((i) => (i + 1) % Math.max(moviesArticles.length, 1));
    }, SECTION_ROTATE_MS);
    return () => window.clearInterval(interval);
  }, [businessArticles.length, sportsArticles.length, crimeArticles.length, moviesArticles.length]);

  // ── Derived visible articles ──
  const activeBreaking =
    breakingArticles[breakingIndex % Math.max(breakingArticles.length, 1)];

  const activeTicker =
    breakingArticles[tickerIndex % Math.max(breakingArticles.length, 1)];

  const visibleBusiness = useMemo(
    () => rotateSlice(businessArticles, businessIndex, 3),
    [businessArticles, businessIndex],
  );
  const visibleSports = useMemo(
    () => rotateSlice(sportsArticles, sportsIndex, 4),
    [sportsArticles, sportsIndex],
  );
  const visibleCrime = useMemo(
    () => rotateSlice(crimeArticles, crimeIndex, 1)[0],
    [crimeArticles, crimeIndex],
  );
  const visibleMovie = useMemo(
    () => rotateSlice(moviesArticles, moviesIndex, 1)[0],
    [moviesArticles, moviesIndex],
  );

  const sectionArticles = useMemo(
    () =>
      selectedSection
        ? selectedSection === "breaking"
          ? breakingArticles
          : grouped[selectedSection]
        : [],
    [selectedSection, breakingArticles, grouped],
  );

  // ── Handlers ──
  const openSection = useCallback((category: Category) => {
    setSelectedSection(category);
    setMenuOpen(false);
  }, []);

  const openArticle = useCallback(
    (article: (typeof articles)[number], section?: Category) => {
      if (!hasValidAiSummary(article)) return;

      const finalSection = section || normalizeCategory(article.category);
      const list = articlesForSection(finalSection);
      const idx = Math.max(0, list.findIndex((item) => item.id === article.id));

      setActiveArticle({ article, section: finalSection, index: idx });
      setSelectedSection(null);
    },
    [articlesForSection],
  );

  const moveArticle = useCallback(
    (direction: "prev" | "next") => {
      if (!activeArticle) return;

      const list = articlesForSection(activeArticle.section);
      if (!list.length) return;

      const currentIndex = list.findIndex(
        (item) => item.id === activeArticle.article.id,
      );
      if (currentIndex < 0) return;

      const nextIndex =
        direction === "next"
          ? (currentIndex + 1) % list.length
          : (currentIndex - 1 + list.length) % list.length;

      setActiveArticle({
        article: list[nextIndex],
        section: activeArticle.section,
        index: nextIndex,
      });
    },
    [activeArticle, articlesForSection],
  );

  return (
    <div className={theme === "dark" ? "tv-root tv-dark" : "tv-root"}>
      <style jsx global>{`
        html,
        body {
          background: #ffffff;
        }

        body:has(.tv-dark) {
          background: #120f1a;
        }

        /* Noto Sans Telugu, not Ramabhadra: Ramabhadra ships weight 400 only,
           so font-weight:700 was synthetic bold — smeared conjuncts. */
        /* Telugu marks sit above the Latin ascender (ీ ై ొ), so the first line
           needs headroom or overflow:hidden shears it. padding-TOP only —
           padding-bottom must never be added here: line-clamp hides the lines
           past the limit by clipping at the padding box, so bottom padding
           uncovers the top of the next line instead of protecting descenders.
           Descenders are handled by line-height instead. */
        .font-news-headline,
        .font-news-summary {
          font-family: "Noto Sans Telugu", Gautami, sans-serif;
          padding-top: 0.2em;
        }

        .font-news-headline {
          font-weight: 700;
        }

        .font-news-summary {
          font-weight: 400;
        }

        .line-clamp-1,
        .line-clamp-2,
        .line-clamp-3,
        .line-clamp-4,
        .line-clamp-5,
        .line-clamp-6 {
          display: -webkit-box;
          -webkit-box-orient: vertical;
          overflow: hidden;
        }

        .line-clamp-1 {
          -webkit-line-clamp: 1;
        }
        .line-clamp-2 {
          -webkit-line-clamp: 2;
        }
        .line-clamp-3 {
          -webkit-line-clamp: 3;
        }
        .line-clamp-4 {
          -webkit-line-clamp: 4;
        }
        .line-clamp-5 {
          -webkit-line-clamp: 5;
        }
        .line-clamp-6 {
          -webkit-line-clamp: 6;
        }

        .hide-scrollbar {
          scrollbar-width: none;
        }

        .hide-scrollbar::-webkit-scrollbar {
          display: none;
        }

        .blink-dot {
          animation: blinkDot 1s infinite;
        }

        @keyframes blinkDot {
          0%,
          100% {
            opacity: 1;
          }
          50% {
            opacity: 0.25;
          }
        }
      `}</style>

      <MobileLayout
        loading={loading}
        error={error}
        menuOpen={menuOpen}
        setMenuOpen={setMenuOpen}
        theme={theme}
        onToggleTheme={toggleTheme}
        mounted={mounted}
        tickerArticle={activeTicker}
        breakingArticle={activeBreaking}
        businessArticles={visibleBusiness}
        sportsArticles={visibleSports.slice(0, 3)}
        crimeArticle={visibleCrime}
        movieArticle={visibleMovie}
        onOpenArticle={openArticle}
        onOpenSection={openSection}
        onPullRefresh={refetch}
      />

      <DesktopLayout
        loading={loading}
        error={error}
        theme={theme}
        onToggleTheme={toggleTheme}
        mounted={mounted}
        tickerArticle={activeTicker}
        breakingArticle={activeBreaking}
        businessArticles={visibleBusiness}
        sportsArticles={visibleSports}
        crimeArticle={visibleCrime}
        movieArticle={visibleMovie}
        onOpenArticle={openArticle}
        onOpenSection={openSection}
      />

      {selectedSection && (
        <SectionModal
          category={selectedSection}
          articles={sectionArticles.filter(hasValidAiSummary)}
          onClose={() => setSelectedSection(null)}
          onOpenArticle={(article) => openArticle(article, selectedSection)}
        />
      )}

      {activeArticle && (
        <ArticleModal
          active={activeArticle}
          total={articlesForSection(activeArticle.section).length}
          onClose={() => setActiveArticle(null)}
          onPrev={() => moveArticle("prev")}
          onNext={() => moveArticle("next")}
        />
      )}
    </div>
  );
}
