"use client";

import { useState } from "react";
import Link from "next/link";
import { CATEGORIES, LABELS } from "../constants";
import { adminFetch, mediaUrl, type AdminArticle } from "./api";

const MAX_UPLOAD_MB = 3;

export function Editor({
  token,
  article,
  onSaved,
  onAuthError,
}: {
  token: string;
  article: AdminArticle | null;
  onSaved: () => void;
  onAuthError: (error: unknown) => void;
}) {
  const isNew = article === null;
  const isFeed = article !== null && !article.is_original;

  const [title, setTitle] = useState(article?.title ?? "");
  const [category, setCategory] = useState(article?.category ?? "breaking");
  const [author, setAuthor] = useState(article?.author ?? "");
  const [summary, setSummary] = useState(article?.is_original ? (article.summary ?? "") : "");
  const [body, setBody] = useState(article?.ai_summary ?? "");
  const [image, setImage] = useState(article?.image ?? "");
  const [imageDirty, setImageDirty] = useState(false);
  const [status, setStatus] = useState<"published" | "draft">(article?.status ?? "published");
  const [confirmed, setConfirmed] = useState(false);

  const [uploading, setUploading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function upload(file: File) {
    setError("");
    if (file.size > MAX_UPLOAD_MB * 1024 * 1024) {
      setError(`Image is over ${MAX_UPLOAD_MB} MB. Resize it first.`);
      return;
    }
    setUploading(true);
    try {
      const result = await adminFetch<{ url: string }>(token, "/admin/media", {
        method: "POST",
        body: file,
        headers: { "Content-Type": file.type || "application/octet-stream" },
      });
      setImage(result.url);
      setImageDirty(true);
    } catch (err) {
      onAuthError(err);
      setError(err instanceof Error ? err.message : "Upload failed.");
    } finally {
      setUploading(false);
    }
  }

  async function save(event: React.FormEvent) {
    event.preventDefault();
    setError("");

    if (isNew && !confirmed) {
      setError("Tick the originality confirmation before publishing.");
      return;
    }

    setSaving(true);
    try {
      if (isNew) {
        await adminFetch(token, "/admin/articles", {
          method: "POST",
          body: JSON.stringify({
            title,
            category,
            author: author || null,
            summary: summary || null,
            body,
            image: image || null,
            status,
            originality_confirmed: confirmed,
          }),
        });
      } else {
        // Send only what changed, so an untouched field never trips validation.
        const patch: Record<string, unknown> = {};
        if (title !== (article.title ?? "")) patch.title = title;
        if (category !== article.category) patch.category = category;
        if (body !== (article.ai_summary ?? "")) patch.body = body;
        if (status !== article.status) patch.status = status;
        if (!isFeed) {
          if (author !== (article.author ?? "")) patch.author = author || null;
          if (summary !== (article.summary ?? "")) patch.summary = summary || null;
        }
        // Feed rows keep their publisher image unless an editor replaces it.
        if (imageDirty) patch.image = image;
        await adminFetch(token, `/admin/articles/${article.id}`, {
          method: "PUT",
          body: JSON.stringify(patch),
        });
      }
      onSaved();
    } catch (err) {
      onAuthError(err);
      setError(err instanceof Error ? err.message : "Save failed.");
    } finally {
      setSaving(false);
    }
  }

  const input =
    "mt-1.5 w-full rounded-md border border-slate-300 bg-white px-3 py-2 outline-none focus:border-red-600";
  const label = "block text-sm font-bold text-slate-700";

  return (
    <form onSubmit={save} className="grid gap-6 lg:grid-cols-[1fr_320px]">
      <section className="space-y-5 rounded-xl border border-slate-200 bg-white p-5">
        <div>
          <h2 className="text-xl font-black">
            {isNew ? "Write a Red4ce article" : `Edit article #${article.id}`}
          </h2>
          {isFeed && (
            <p className="mt-1 text-sm text-slate-500">
              Feed article from {article.source}. Edits change how it shows on Red4ce only.
            </p>
          )}
        </div>

        <div>
          <label htmlFor="ed-title" className={label}>
            Headline
          </label>
          <input
            id="ed-title"
            required
            minLength={3}
            maxLength={300}
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            className={`${input} font-news-headline text-lg`}
          />
        </div>

        {!isFeed && (
          <div>
            <label htmlFor="ed-summary" className={label}>
              Short summary <span className="font-normal text-slate-400">(optional, shown in lists)</span>
            </label>
            <textarea
              id="ed-summary"
              maxLength={600}
              rows={2}
              value={summary}
              onChange={(e) => setSummary(e.target.value)}
              className={`${input} font-news-summary`}
            />
          </div>
        )}

        <div>
          <label htmlFor="ed-body" className={label}>
            Article
          </label>
          <textarea
            id="ed-body"
            required
            minLength={40}
            maxLength={20000}
            rows={16}
            value={body}
            onChange={(e) => setBody(e.target.value)}
            className={`${input} font-news-summary leading-7`}
          />
          <p className="mt-1 text-xs text-slate-400">
            {body.trim().length.toLocaleString()} / 20,000 characters · minimum 40
          </p>
        </div>
      </section>

      <aside className="space-y-5">
        <section className="space-y-4 rounded-xl border border-slate-200 bg-white p-5">
          <div>
            <label htmlFor="ed-category" className={label}>
              Section
            </label>
            <select
              id="ed-category"
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              className={input}
            >
              {CATEGORIES.map((c) => (
                <option key={c} value={c}>
                  {LABELS[c]}
                </option>
              ))}
            </select>
          </div>

          {!isFeed && (
            <div>
              <label htmlFor="ed-author" className={label}>
                Byline
              </label>
              <input
                id="ed-author"
                maxLength={80}
                value={author}
                onChange={(e) => setAuthor(e.target.value)}
                className={input}
              />
            </div>
          )}

          <fieldset>
            <legend className={label}>Status</legend>
            <div className="mt-2 flex gap-2">
              {(["published", "draft"] as const).map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => setStatus(s)}
                  aria-pressed={status === s}
                  className={`flex-1 rounded-md border px-3 py-2 text-sm font-bold capitalize ${
                    status === s
                      ? "border-slate-900 bg-slate-900 text-white"
                      : "border-slate-300 text-slate-600"
                  }`}
                >
                  {s}
                </button>
              ))}
            </div>
          </fieldset>
        </section>

        <section className="space-y-3 rounded-xl border border-slate-200 bg-white p-5">
          <p className={label}>Photo</p>
          {image ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={mediaUrl(image)} alt="" className="aspect-video w-full rounded-md bg-slate-100 object-cover" />
          ) : (
            <div className="flex aspect-video w-full items-center justify-center rounded-md bg-slate-100 text-sm text-slate-400">
              No photo
            </div>
          )}
          <label className="block cursor-pointer rounded-md border border-dashed border-slate-300 px-3 py-2 text-center text-sm font-bold text-slate-600 hover:border-red-600 hover:text-red-600">
            {uploading ? "Uploading…" : "Upload our photo (JPEG, PNG, WebP, ≤3 MB)"}
            <input
              type="file"
              accept="image/jpeg,image/png,image/webp,image/gif"
              className="sr-only"
              disabled={uploading}
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) void upload(file);
                e.target.value = "";
              }}
            />
          </label>
          {image && (
            <button
              type="button"
              onClick={() => {
                setImage("");
                setImageDirty(true);
              }}
              className="w-full text-sm font-bold text-slate-500 hover:text-red-600"
            >
              Remove photo
            </button>
          )}
        </section>

        {isNew && (
          <label className="flex gap-3 rounded-xl border border-amber-300 bg-amber-50 p-4 text-sm text-amber-950">
            <input
              type="checkbox"
              checked={confirmed}
              onChange={(e) => setConfirmed(e.target.checked)}
              className="mt-0.5 h-4 w-4 shrink-0 accent-red-600"
            />
            <span>
              This text and photo are our own work, or we hold written rights to them. Nothing is
              copied from another publication.{" "}
              <Link href="/policy#editorial" target="_blank" className="font-bold underline">
                Editorial policy
              </Link>
            </span>
          </label>
        )}

        {error && (
          <p role="alert" className="rounded-md bg-red-50 p-3 text-sm font-semibold text-red-700">
            {error}
          </p>
        )}

        <button
          type="submit"
          disabled={saving || uploading}
          className="w-full rounded-md bg-red-600 py-3 font-black text-white transition hover:bg-red-700 disabled:opacity-60"
        >
          {saving ? "Saving…" : isNew ? (status === "draft" ? "Save draft" : "Publish") : "Save changes"}
        </button>
      </aside>
    </form>
  );
}
