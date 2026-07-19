import { memo } from "react";

export const EmptyText = memo(function EmptyText({ text }: { text: string }) {
  return (
    <div className="flex h-[calc(100%-42px)] items-center justify-center rounded-md bg-slate-50 p-4 text-center text-[12px] font-bold text-slate-400">
      {text}
    </div>
  );
});

export const MobileEmpty = memo(function MobileEmpty({ text }: { text: string }) {
  return (
    <div className="rounded-xl bg-slate-50 p-4 text-center text-[12px] font-bold text-slate-400">
      {text}
    </div>
  );
});
