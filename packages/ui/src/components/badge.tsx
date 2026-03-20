import type { HTMLAttributes, PropsWithChildren } from "react";

import { cn } from "../lib/cn";

export function Badge({
  className,
  children,
  ...props
}: PropsWithChildren<HTMLAttributes<HTMLSpanElement>>) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border border-white/70 bg-white/[0.68] px-3 py-1.5 text-xs font-medium text-slate-700 backdrop-blur-md",
        className,
      )}
      {...props}
    >
      {children}
    </span>
  );
}
