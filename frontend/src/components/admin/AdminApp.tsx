"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { adminFetch, AdminError, type AdminArticle } from "./api";
import { Editor } from "./Editor";
import { Manage } from "./Manage";
import { Analytics } from "./Analytics";
import { AuditLog } from "./AuditLog";

type Tab = "write" | "manage" | "analytics" | "security";

const TABS: { id: Tab; label: string }[] = [
  { id: "write", label: "Write" },
  { id: "manage", label: "Manage & search" },
  { id: "analytics", label: "Analytics" },
  { id: "security", label: "Security log" },
];

// sessionStorage, not localStorage: the token is gone when the tab closes.
const TOKEN_KEY = "r4-admin-token";

export function AdminApp() {
  const [token, setToken] = useState<string | null>(null);
  const [checked, setChecked] = useState(false);
  const [tab, setTab] = useState<Tab>("write");
  const [editing, setEditing] = useState<AdminArticle | null>(null);

  useEffect(() => {
    try {
      setToken(window.sessionStorage.getItem(TOKEN_KEY));
    } catch {
      // storage blocked: log in every visit
    }
    setChecked(true);
  }, []);

  const signOut = useCallback(() => {
    try {
      window.sessionStorage.removeItem(TOKEN_KEY);
    } catch {
      // ignore
    }
    setToken(null);
    setEditing(null);
  }, []);

  // Any 401 from a tab means the token stopped working: drop it.
  const onAuthError = useCallback(
    (error: unknown) => {
      if (error instanceof AdminError && error.status === 401) signOut();
    },
    [signOut],
  );

  if (!checked) return null;

  if (!token) {
    return (
      <Login
        onLogin={(value) => {
          try {
            window.sessionStorage.setItem(TOKEN_KEY, value);
          } catch {
            // ignore
          }
          setToken(value);
        }}
      />
    );
  }

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-4 px-4 py-3">
          <Link href="/" className="text-2xl font-black tracking-tight">
            <span className="text-red-600">Red</span>4ce
          </Link>
          <span className="text-xs font-bold uppercase tracking-[0.2em] text-slate-400">
            Newsroom
          </span>
          <nav className="flex flex-wrap gap-1" aria-label="Newsroom sections">
            {TABS.map((t) => (
              <button
                key={t.id}
                type="button"
                onClick={() => {
                  setTab(t.id);
                  if (t.id === "write") setEditing(null);
                }}
                className={`rounded-md px-3 py-1.5 text-sm font-bold transition ${
                  tab === t.id ? "bg-slate-900 text-white" : "text-slate-600 hover:bg-slate-100"
                }`}
              >
                {t.label}
              </button>
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-3 text-sm">
            <Link href="/policy" className="font-bold text-slate-500 hover:text-red-600">
              Policy
            </Link>
            <button
              type="button"
              onClick={signOut}
              className="rounded-md border border-slate-300 px-3 py-1.5 font-bold hover:border-red-600 hover:text-red-600"
            >
              Sign out
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-4 py-6">
        {tab === "write" && (
          <Editor
            key={editing?.id ?? "new"}
            token={token}
            article={editing}
            onAuthError={onAuthError}
            onSaved={() => {
              setEditing(null);
              setTab("manage");
            }}
          />
        )}
        {tab === "manage" && (
          <Manage
            token={token}
            onAuthError={onAuthError}
            onEdit={(article) => {
              setEditing(article);
              setTab("write");
            }}
          />
        )}
        {tab === "analytics" && <Analytics token={token} onAuthError={onAuthError} />}
        {tab === "security" && <AuditLog token={token} onAuthError={onAuthError} />}
      </main>
    </div>
  );
}

function Login({ onLogin }: { onLogin: (token: string) => void }) {
  const [value, setValue] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    const candidate = value.trim();
    if (!candidate) return;
    setBusy(true);
    setError("");
    try {
      await adminFetch(candidate, "/admin/me");
      onLogin(candidate);
    } catch (err) {
      setError(
        err instanceof AdminError && err.status === 401
          ? "That token is not valid."
          : err instanceof Error
            ? err.message
            : "Could not reach the API.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4 text-slate-900">
      <form
        onSubmit={submit}
        className="w-full max-w-sm rounded-xl border border-slate-200 bg-white p-6 shadow-sm"
      >
        <p className="text-3xl font-black tracking-tight">
          <span className="text-red-600">Red</span>4ce
        </p>
        <h1 className="mt-1 text-sm font-bold uppercase tracking-[0.2em] text-slate-400">
          Newsroom sign in
        </h1>
        <label htmlFor="admin-token" className="mt-6 block text-sm font-bold">
          Admin token
        </label>
        <input
          id="admin-token"
          type="password"
          autoComplete="current-password"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          className="mt-2 w-full rounded-md border border-slate-300 px-3 py-2 outline-none focus:border-red-600"
        />
        {error && (
          <p role="alert" className="mt-3 text-sm font-semibold text-red-700">
            {error}
          </p>
        )}
        <button
          type="submit"
          disabled={busy}
          className="mt-5 w-full rounded-md bg-slate-900 py-2.5 font-black text-white transition hover:bg-red-600 disabled:opacity-60"
        >
          {busy ? "Checking…" : "Sign in"}
        </button>
        <p className="mt-4 text-xs text-slate-500">
          Five wrong tokens lock this network out for 15 minutes.
        </p>
      </form>
    </div>
  );
}
