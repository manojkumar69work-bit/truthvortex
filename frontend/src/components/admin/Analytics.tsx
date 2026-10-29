"use client";

import { useEffect, useState } from "react";
import { LABELS } from "../constants";
import { adminFetch } from "./api";

type Summary = {
  days: number;
  totals: { pageviews: number; article_views: number; source_clicks: number; visitors: number };
  daily: { day: string; pageviews: number; article_views: number; visitors: number }[];
  top_articles: {
    article_id: number;
    title: string | null;
    source: string | null;
    is_original: boolean | null;
    category: string | null;
    views: number;
  }[];
  categories: { category: string; views: number }[];
  referrers: { referrer: string; visits: number }[];
  devices: { device: string; visitors: number }[];
  content: { total: number; originals: number; drafts: number };
  sources: { source: string; articles: number }[];
};

const RANGES = [1, 7, 30, 90] as const;

export function Analytics({
  token,
  onAuthError,
}: {
  token: string;
  onAuthError: (error: unknown) => void;
}) {
  const [days, setDays] = useState<number>(7);
  const [data, setData] = useState<Summary | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let live = true;
    setError("");
    adminFetch<Summary>(token, `/admin/analytics?days=${days}`)
      .then((result) => live && setData(result))
      .catch((err) => {
        onAuthError(err);
        if (live) setError(err instanceof Error ? err.message : "Could not load analytics.");
      });
    return () => {
      live = false;
    };
  }, [token, days, onAuthError]);

  return (
    <section className="space-y-5">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="mr-auto text-xl font-black">Analytics</h2>
        <div role="group" aria-label="Date range" className="flex rounded-md border border-slate-300 bg-white p-0.5">
          {RANGES.map((r) => (
            <button
              key={r}
              type="button"
              aria-pressed={days === r}
              onClick={() => setDays(r)}
              className={`rounded px-3 py-1 text-sm font-bold ${
                days === r ? "bg-slate-900 text-white" : "text-slate-600"
              }`}
            >
              {r === 1 ? "24h" : `${r}d`}
            </button>
          ))}
        </div>
      </div>

      {error && (
        <p role="alert" className="rounded-md bg-red-50 p-3 text-sm font-semibold text-red-700">
          {error}
        </p>
      )}

      {data && (
        <>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <Stat label="Visitors" value={data.totals.visitors} />
            <Stat label="Page views" value={data.totals.pageviews} />
            <Stat label="Articles read" value={data.totals.article_views} />
            <Stat label="Clicks to sources" value={data.totals.source_clicks} />
          </div>

          <Panel title="Page views per day">
            <DailyBars daily={data.daily} />
          </Panel>

          <div className="grid gap-5 lg:grid-cols-2">
            <Panel title="Most-read articles">
              <RankList
                rows={data.top_articles.map((a) => ({
                  key: String(a.article_id),
                  label: a.title ?? `#${a.article_id} (deleted or expired)`,
                  note: a.is_original ? "Red4ce Original" : (a.source ?? ""),
                  value: a.views,
                }))}
                empty="No article views yet."
              />
            </Panel>
            <Panel title="Reads by section">
              <RankList
                rows={data.categories.map((c) => ({
                  key: c.category,
                  label: LABELS[c.category] ?? c.category,
                  value: c.views,
                }))}
                empty="No article views yet."
              />
            </Panel>
            <Panel title="Where visitors come from">
              <RankList
                rows={data.referrers.map((r) => ({ key: r.referrer, label: r.referrer, value: r.visits }))}
                empty="No external referrers yet (direct visits are not listed)."
              />
            </Panel>
            <Panel title="Devices (visitors)">
              <RankList
                rows={data.devices.map((d) => ({ key: d.device, label: d.device, value: d.visitors }))}
                empty="No visits yet."
              />
            </Panel>
          </div>

          <Panel title="Content in the database">
            <div className="mb-4 grid grid-cols-3 gap-3">
              <Stat label="Articles" value={data.content.total} />
              <Stat label="Red4ce originals" value={data.content.originals} />
              <Stat label="Hidden / drafts" value={data.content.drafts} />
            </div>
            <RankList
              rows={data.sources.map((s) => ({ key: s.source, label: s.source, value: s.articles }))}
              empty="No articles."
            />
          </Panel>

          <p className="text-xs text-slate-500">
            Cookie-free. Visitors are counted with a daily hash of IP and browser, so one person
            counts once per day and cannot be tracked across days. Bots are ignored. Events older
            than 90 days are deleted.
          </p>
        </>
      )}
    </section>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <p className="text-xs font-bold uppercase tracking-wider text-slate-500">{label}</p>
      <p className="mt-1 text-3xl font-black tabular-nums text-slate-900">{value.toLocaleString()}</p>
    </div>
  );
}

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5">
      <h3 className="mb-4 text-sm font-black uppercase tracking-wider text-slate-500">{title}</h3>
      {children}
    </section>
  );
}

/** Single-series column chart: one hue, 2px gaps, rounded data-end, hover tooltip. */
function DailyBars({ daily }: { daily: Summary["daily"] }) {
  const [hover, setHover] = useState<number | null>(null);
  if (!daily.length) return <p className="text-sm text-slate-400">No visits in this range.</p>;

  const max = Math.max(1, ...daily.map((d) => d.pageviews));
  const active = hover !== null ? daily[hover] : null;

  return (
    <div>
      <p className="mb-2 h-5 text-sm text-slate-600 tabular-nums" aria-live="polite">
        {active
          ? `${active.day} · ${active.pageviews.toLocaleString()} views · ${active.visitors.toLocaleString()} visitors · ${active.article_views.toLocaleString()} reads`
          : `Peak ${max.toLocaleString()} views/day`}
      </p>
      <div
        className="flex h-40 items-end gap-[2px] border-b border-slate-200"
        onMouseLeave={() => setHover(null)}
      >
        {daily.map((d, i) => (
          <button
            key={d.day}
            type="button"
            aria-label={`${d.day}: ${d.pageviews} page views`}
            onMouseEnter={() => setHover(i)}
            onFocus={() => setHover(i)}
            className="group flex h-full min-w-0 flex-1 items-end"
          >
            <span
              className={`w-full rounded-t-[4px] ${hover === i ? "bg-red-700" : "bg-red-500"}`}
              style={{ height: `${Math.max(2, (d.pageviews / max) * 100)}%` }}
            />
          </button>
        ))}
      </div>
      <div className="mt-1 flex justify-between text-xs text-slate-400 tabular-nums">
        <span>{daily[0].day}</span>
        <span>{daily[daily.length - 1].day}</span>
      </div>
      <details className="mt-3 text-sm">
        <summary className="cursor-pointer font-bold text-slate-500">Show as table</summary>
        <table className="mt-2 w-full text-left tabular-nums">
          <thead className="text-xs uppercase text-slate-500">
            <tr>
              <th className="py-1">Day</th>
              <th>Page views</th>
              <th>Visitors</th>
              <th>Reads</th>
            </tr>
          </thead>
          <tbody>
            {daily.map((d) => (
              <tr key={d.day} className="border-t border-slate-100">
                <td className="py-1">{d.day}</td>
                <td>{d.pageviews}</td>
                <td>{d.visitors}</td>
                <td>{d.article_views}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </div>
  );
}

function RankList({
  rows,
  empty,
}: {
  rows: { key: string; label: string; note?: string; value: number }[];
  empty: string;
}) {
  if (!rows.length) return <p className="text-sm text-slate-400">{empty}</p>;
  const max = Math.max(1, ...rows.map((r) => r.value));
  return (
    <ol className="space-y-2.5">
      {rows.map((r) => (
        <li key={r.key} title={`${r.label}: ${r.value.toLocaleString()}`}>
          <div className="flex items-baseline justify-between gap-3 text-sm">
            <span className="font-news-headline min-w-0 truncate font-semibold text-slate-800">
              {r.label}
              {r.note && <span className="ml-2 text-xs font-normal text-slate-400">{r.note}</span>}
            </span>
            <span className="shrink-0 font-bold tabular-nums text-slate-700">{r.value.toLocaleString()}</span>
          </div>
          <div className="mt-1 h-1.5 rounded-full bg-slate-100">
            <div className="h-full rounded-full bg-red-500" style={{ width: `${(r.value / max) * 100}%` }} />
          </div>
        </li>
      ))}
    </ol>
  );
}
