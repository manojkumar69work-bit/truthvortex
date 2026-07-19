"use client";

import { memo } from "react";
import type { Theme } from "./types";

function ThemeToggleComponent({ theme, onToggle }: { theme: Theme; onToggle: () => void }) {
  return (
    <button
      type="button"
      onClick={onToggle}
      aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
      title={theme === "dark" ? "Light mode" : "Dark mode"}
      className="flex h-11 w-11 items-center justify-center rounded-xl border border-slate-200 bg-white text-[18px] text-[#071225] shadow-[0_8px_20px_rgba(15,23,42,0.08)] transition hover:text-red-600 active:scale-95"
    >
      {theme === "dark" ? "☀" : "☾"}
    </button>
  );
}

export const ThemeToggle = memo(ThemeToggleComponent);
