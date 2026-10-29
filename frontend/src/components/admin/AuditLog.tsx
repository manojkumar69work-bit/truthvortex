"use client";

import { useEffect, useState } from "react";
import { adminFetch, formatDate } from "./api";

type Entry = {
  id: number;
  ts: string;
  action: string;
  article_id: number | null;
  detail: string | null;
  ip: string | null;
};

export function AuditLog({
  token,
  onAuthError,
}: {
  token: string;
  onAuthError: (error: unknown) => void;
}) {
  const [entries, setEntries] = useState<Entry[] | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    adminFetch<Entry[]>(token, "/admin/audit?limit=100")
      .then(setEntries)
      .catch((err) => {
        onAuthError(err);
        setError(err instanceof Error ? err.message : "Could not load the log.");
      });
  }, [token, onAuthError]);

  return (
    <section className="space-y-4">
      <div>
        <h2 className="text-xl font-black">Security log</h2>
        <p className="mt-1 text-sm text-slate-500">
          Every create, edit, delete and upload made in the newsroom, newest first.
        </p>
      </div>
      {error && (
        <p role="alert" className="rounded-md bg-red-50 p-3 text-sm font-semibold text-red-700">
          {error}
        </p>
      )}
      <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
        <table className="w-full min-w-[640px] text-left text-sm">
          <thead className="border-b border-slate-200 text-xs uppercase tracking-wider text-slate-500">
            <tr>
              <th className="px-4 py-3">When</th>
              <th className="px-3 py-3">Action</th>
              <th className="px-3 py-3">Article</th>
              <th className="px-3 py-3">Detail</th>
              <th className="px-4 py-3">IP</th>
            </tr>
          </thead>
          <tbody>
            {(entries ?? []).map((e) => (
              <tr key={e.id} className="border-b border-slate-100 last:border-0">
                <td className="whitespace-nowrap px-4 py-2.5 text-slate-500">{formatDate(e.ts)}</td>
                <td className="px-3 py-2.5 font-bold capitalize">{e.action}</td>
                <td className="px-3 py-2.5 tabular-nums">{e.article_id ? `#${e.article_id}` : "—"}</td>
                <td className="max-w-[360px] truncate px-3 py-2.5 text-slate-600">{e.detail}</td>
                <td className="px-4 py-2.5 font-mono text-xs text-slate-500">{e.ip}</td>
              </tr>
            ))}
            {entries && entries.length === 0 && (
              <tr>
                <td colSpan={5} className="px-4 py-10 text-center text-slate-400">
                  No newsroom activity yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
