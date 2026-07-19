"use client";

import { memo, type ReactNode } from "react";
import { SafeImage } from "./SafeImage";
import { getImage } from "./utils";
import type { Article } from "./types";

export const CardShell = memo(function CardShell({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={`overflow-hidden rounded-xl border border-slate-200/90 bg-white shadow-[0_10px_28px_rgba(15,23,42,0.06)] transition duration-300 hover:shadow-[0_18px_40px_rgba(15,23,42,0.1)] ${className}`}
    >
      {children}
    </div>
  );
});

export const CardHeader = memo(function CardHeader({
  title,
  onOpenSection,
}: {
  title: string;
  onOpenSection: () => void;
}) {
  return (
    <div className="mb-3 flex h-[34px] items-center justify-between gap-3 border-b border-slate-100 pb-3">
      <div className="flex min-w-0 items-center gap-2">
        <span className="h-5 w-1 rounded-sm bg-red-600" />
        <h2 className="truncate text-[14px] font-black uppercase tracking-[0.2em] text-[#071225]">
          {title}
        </h2>
      </div>
      <button
        type="button"
        onClick={onOpenSection}
        className="shrink-0 rounded-md px-3 py-1.5 text-[11px] font-black uppercase tracking-[0.12em] text-red-600 transition hover:bg-red-50 hover:text-red-700"
      >
        View All →
      </button>
    </div>
  );
});

export const ImageBox = memo(function ImageBox({ article }: { article: Article }) {
  return (
    <div className="h-full w-full overflow-hidden rounded-md bg-slate-100 shadow-[inset_0_0_0_1px_rgba(15,23,42,0.04)]">
      <SafeImage
        src={getImage(article)}
        className="h-full w-full object-cover transition duration-500 group-hover:scale-105"
      />
    </div>
  );
});
