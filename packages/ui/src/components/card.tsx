import type { HTMLAttributes, PropsWithChildren } from "react";

import { cn } from "../lib/cn";

export function Card({ className, children, ...props }: PropsWithChildren<HTMLAttributes<HTMLDivElement>>) {
  return (
    <div
      className={cn(
        "surface-panel rounded-[30px] border border-white/[0.65] p-6 shadow-[0_20px_54px_rgba(15,23,42,0.08)] transition-[transform,box-shadow,border-color,background-color] duration-300 md:p-7",
        className,
      )}
      {...props}
    >
      {children}
    </div>
  );
}
