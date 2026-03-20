import type { InputHTMLAttributes } from "react";

import { cn } from "../lib/cn";

export function Input({ className, ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={cn(
        "h-12 w-full rounded-[22px] border border-white/70 bg-white/[0.72] px-4 text-sm text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-[var(--accent)] focus:bg-white focus:ring-4 focus:ring-[rgba(77,124,255,0.12)]",
        className,
      )}
      {...props}
    />
  );
}
