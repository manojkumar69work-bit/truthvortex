"use client";

import { useState, useEffect, useMemo, useCallback, useRef } from "react";
import { API_URL, REFRESH_MS } from "./constants";
import { normalizeCategory, hasValidAiSummary } from "./utils";
import type { Article, Category } from "./types";

export function useNews() {
  const [articles, setArticles] = useState<Article[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // Guards against out-of-order responses: a slow first request must not
  // overwrite the result of a later one that already came back.
  const requestId = useRef(0);

  const fetchNews = useCallback(async () => {
    if (typeof document !== "undefined" && document.hidden) {
      // Nothing is in flight, so stop waiting on one. Returning without this
      // left `loading` true forever when the page was first opened in a
      // background tab, pinning the skeleton until the tab was focused.
      setLoading(false);
      return;
    }

    const id = ++requestId.current;

    try {
      setError("");

      const response = await fetch(API_URL, { cache: "no-store" });

      if (!response.ok) {
        throw new Error(`API error: ${response.status}`);
      }

      const data = await response.json();

      const cleanArticles = Array.isArray(data)
        ? data.filter((item): item is Article => {
            return (
              item &&
              typeof item.id === "number" &&
              typeof item.title === "string" &&
              item.title.trim().length > 0
            );
          })
        : [];

      if (id !== requestId.current) return;

      setArticles(cleanArticles);
    } catch (err) {
      if (id !== requestId.current) return;

      setError(err instanceof Error ? err.message : "Unable to fetch news");
    } finally {
      if (id === requestId.current) {
        setLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    fetchNews();

    const handleVisibilityChange = () => {
      if (!document.hidden) {
        fetchNews();
      }
    };

    const interval = window.setInterval(fetchNews, REFRESH_MS);

    document.addEventListener("visibilitychange", handleVisibilityChange);

    return () => {
      window.clearInterval(interval);
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, [fetchNews]);

  const grouped = useMemo(() => {
    const result: Record<Category, Article[]> = {
      breaking: [],
      business: [],
      sports: [],
      crime: [],
      movies: [],
    };

    for (const article of articles) {
      result[normalizeCategory(article.category)].push(article);
    }

    return result;
  }, [articles]);

  // Only articles with a usable AI summary can actually be opened —
  // openArticle() refuses the rest. The layouts were being handed the
  // *unfiltered* lists, so a card could render an article that did nothing
  // when clicked. Display and click have to come from the same list.
  const displayable = useMemo(() => {
    const result: Record<Category, Article[]> = {
      breaking: [],
      business: [],
      sports: [],
      crime: [],
      movies: [],
    };

    for (const category of Object.keys(result) as Category[]) {
      result[category] = grouped[category].filter(hasValidAiSummary);
    }

    return result;
  }, [grouped]);

  const breakingArticles = displayable.breaking;
  const businessArticles = displayable.business;
  const sportsArticles = displayable.sports;
  const crimeArticles = displayable.crime;
  const moviesArticles = displayable.movies;

  function articlesForSection(section: Category) {
    return displayable[section];
  }

  return {
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
    refetch: fetchNews,
  };
}
