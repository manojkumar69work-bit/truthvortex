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

  const breakingArticles = grouped.breaking;
  const businessArticles = grouped.business;
  const sportsArticles = grouped.sports;
  const crimeArticles = grouped.crime;
  const moviesArticles = grouped.movies;

  function articlesForSection(section: Category) {
    if (section === "breaking") return breakingArticles.filter(hasValidAiSummary);
    return grouped[section].filter(hasValidAiSummary);
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
