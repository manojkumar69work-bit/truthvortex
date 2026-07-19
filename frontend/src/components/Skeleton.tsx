import { memo } from "react";

export const SkeletonRows = memo(function SkeletonRows({ count }: { count: number }) {
  return (
    <div className="space-y-3">
      {Array.from({ length: count }).map((_, index) => (
        <div key={index} className="grid grid-cols-[112px_1fr] gap-3">
          <div className="h-11 animate-pulse rounded-md bg-slate-100" />
          <div className="space-y-2 self-center">
            <div className="h-3 w-3/4 animate-pulse rounded-sm bg-slate-200" />
            <div className="h-3 w-1/2 animate-pulse rounded-sm bg-slate-100" />
          </div>
        </div>
      ))}
    </div>
  );
});

export const SkeletonCards = memo(function SkeletonCards({ count }: { count: number }) {
  return (
    <div className="grid grid-cols-3 gap-3">
      {Array.from({ length: count }).map((_, index) => (
        <div key={index}>
          <div className="h-[96px] animate-pulse rounded-lg bg-slate-100" />
          <div className="mt-2 h-3 animate-pulse rounded bg-slate-100" />
          <div className="mt-2 h-3 w-2/3 animate-pulse rounded bg-slate-100" />
        </div>
      ))}
    </div>
  );
});
