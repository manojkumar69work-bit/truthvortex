"use client";

import { useCallback, useEffect, useState } from "react";
import { CATEGORIES, LABELS } from "../constants";
import { adminFetch, formatDate, type AdminArticle } from "./api";

const PAGE = 25;

type Filters = {
  q: string;
  category: string;
  origin: "all" | "original" | "feed";
  status: "all" | "published" | "draft";
};

export function Manage({
  token,
  onEdit,
  onAuthError,
}: {
  token: string;
  onEdit: (article: AdminArticle) => void;
  onAuthError: (error: unknown) => void;
}) {
  const [filters, setFilters] = useState<Filters>({
    q: "",
    category: "",
    origin: "all",
    status: "all",
  });
  const [query, setQuery] = useState("");
  const [offset, setOffset] = useState(0);
  const [items, setItems] = useState<AdminArticle[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState<number | null>(null);

  // Debounce typing into the search box.
  useEffect(() => {
    const timer = window.setTimeout(() => {
      setFilters((f) => (f.q === query ? f : { ...f, q: query }));
      setOffset(0);
    }, 300);
    return () => window.clearTimeout(timer);
  }, [query]);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    const params = new URLSearchParams({
      q: filters.q,
      category: filters.category,
      origin: filters.origin,
      status: filters.status,
      limit: String(PAGE),
      offset: String(offset),
    });
    try {
      const result = await adminFetch<{ total: number; items: AdminArticle[] }>(
        token,
        `/admin/articles?${params}`,
      );
      setItems(result.items);
      setTotal(result.total);
    } catch (err) {
      onAuthError(err);
      setError(err instanceof Error ? err.message : "Could not load articles.");
    } finally {
      setLoading(false);
    }
  }, [token, filters, offset, onAuthError]);

  useEffect(() => {
    void load();
  }, [load]);

  async function setStatus(article: AdminArticle, status: "published" | "draft") {
    setBusyId(article.id);
    try {
      await adminFetch(token, `/admin/articles/${article.id}`, {
        method: "PUT",
        body: JSON.stringify({ status }),
      });
      await load();
    } catch (err) {
      onAuthError(err);
      setError(err instanceof Error ? err.message : "Update failed.");
    } finally {
      setBusyId(null);
    }
  }

  async function remove(article: AdminArticle) {
    const ok = window.confirm(
      `Delete "${article.title}"?\n\nThis removes it from Red4ce permanently.`,
    );
    if (!ok) return;
    setBusyId(article.id);
    try {
      await adminFetch(token, `/admin/articles/${article.id}`, { method: "DELETE" });
      await load();
    } catch (err) {
      onAuthError(err);
      setError(err instanceof Error ? err.message : "Delete failed.");
    } finally {
      setBusyId(null);
    }
  }

  const select = "rounded-md border border-slate-300 bg-white px-2.5 py-2 text-sm font-semibold";

  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-center gap-2 rounded-xl border border-slate-200 bg-white p-3">
        <input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search headline, text, source, byline or #id"
          aria-label="Search articles"
          className="min-w-[220px] flex-1 rounded-md border border-slate-300 px-3 py-2 outline-none focus:border-red-600"
        />
        <select
          aria-label="Section"
          value={filters.category}
          onChange={(e) => {
            setFilters((f) => ({ ...f, category: e.target.value }));
            setOffset(0);
          }}
          className={select}
        >
          <option value="">All sections</option>
          {CATEGORIES.map((c) => (
            <option key={c} value={c}>
              {LABELS[c]}
            </option>
          ))}
        </select>
        <select
          aria-label="Origin"
          value={filters.origin}
          onChange={(e) => {
            setFilters((f) => ({ ...f, origin: e.target.value as Filters["origin"] }));
            setOffset(0);
          }}
          className={select}
        >
          <option value="all">Ours + feeds</option>
          <option value="original">Red4ce originals</option>
          <option value="feed">Feed articles</option>
        </select>
        <select
          aria-label="Status"
          value={filters.status}
          onChange={(e) => {
            setFilters((f) => ({ ...f, status: e.target.value as Filters["status"] }));
            setOffset(0);
          }}
          className={select}
        >
          <option value="all">Any status</option>
          <option value="published">Published</option>
          <option value="draft">Drafts / hidden</option>
        </select>
      </div>

      {error && (
        <p role="alert" className="rounded-md bg-red-50 p-3 text-sm font-semibold text-red-700">
          {error}
        </p>
      )}

      <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
        <table className="w-full min-w-[760px] text-left text-sm">
          <thead className="border-b border-slate-200 text-xs uppercase tracking-wider text-slate-500">
            <tr>
              <th className="px-4 py-3">Headline</th>
              <th className="px-3 py-3">Source</th>
              <th className="px-3 py-3">Section</th>
              <th className="px-3 py-3">Status</th>
              <th className="px-3 py-3">Published</th>
              <th className="px-4 py-3 text-right">Actions</th>
            </tr>
          </thead>
          <tbody>
            {items.map((a) => (
              <tr key={a.id} className="border-b border-slate-100 align-top last:border-0">
                <td className="max-w-[380px] px-4 py-3">
                  <p className="font-news-headline line-clamp-2 font-bold">{a.title}</p>
                  <p className="mt-0.5 text-xs text-slate-400">
                    #{a.id}
                    {a.author ? ` · ${a.author}` : ""}
                  </p>
                </td>
                <td className="px-3 py-3">
                  {a.is_original ? (
                    <span className="rounded bg-red-600 px-1.5 py-0.5 text-xs font-bold text-white">
                      Original
                    </span>
                  ) : (
                    <span className="text-slate-600">{a.source}</span>
                  )}
                </td>
                <td className="px-3 py-3">{LABELS[a.category ?? ""] ?? a.category}</td>
                <td className="px-3 py-3">
                  <span
                    className={`rounded px-1.5 py-0.5 text-xs font-bold ${
                      a.status === "published"
                        ? "bg-emerald-50 text-emerald-800"
                        : "bg-slate-100 text-slate-600"
                    }`}
                  >
                    {a.status === "published" ? "Live" : "Hidden"}
                  </span>
                </td>
                <td className="whitespace-nowrap px-3 py-3 text-slate-500">
                  {formatDate(a.published)}
                </td>
                <td className="whitespace-nowrap px-4 py-3 text-right">
                  <div className="inline-flex gap-1">
                    <button
                      type="button"
                      onClick={() => onEdit(a)}
                      className="rounded px-2 py-1 font-bold text-slate-700 hover:bg-slate-100"
                    >
                      Edit
                    </button>
                    <button
                      type="button"
                      disabled={busyId === a.id}
                      onClick={() => setStatus(a, a.status === "published" ? "draft" : "published")}
                      className="rounded px-2 py-1 font-bold text-slate-700 hover:bg-slate-100 disabled:opacity-50"
                    >
                      {a.status === "published" ? "Hide" : "Publish"}
                    </button>
                    <button
                      type="button"
                      disabled={busyId === a.id}
                      onClick={() => remove(a)}
                      className="rounded px-2 py-1 font-bold text-red-700 hover:bg-red-50 disabled:opacity-50"
                    >
                      Delete
                    </button>
                  </div>
                </td>
              </tr>
            ))}
            {!loading && items.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-10 text-center text-slate-400">
                  No articles match.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="flex items-center justify-between text-sm text-slate-500">
        <span>
          {loading
            ? "Loading…"
            : total === 0
              ? "0 articles"
              : `${offset + 1}–${Math.min(offset + PAGE, total)} of ${total.toLocaleString()}`}
        </span>
        <div className="flex gap-2">
          <button
            type="button"
            disabled={offset === 0 || loading}
            onClick={() => setOffset(Math.max(0, offset - PAGE))}
            className="rounded-md border border-slate-300 bg-white px-3 py-1.5 font-bold disabled:opacity-40"
          >
            Previous
          </button>
          <button
            type="button"
            disabled={offset + PAGE >= total || loading}
            onClick={() => setOffset(offset + PAGE)}
            className="rounded-md border border-slate-300 bg-white px-3 py-1.5 font-bold disabled:opacity-40"
          >
            Next
          </button>
        </div>
      </div>
    </section>
  );
}
