import type { ReactNode } from "react";

export function SectionHeading({
  eyebrow,
  title,
  description,
  actions,
}: {
  eyebrow?: string;
  title: string;
  description?: string;
  actions?: ReactNode;
}) {
  return (
    <div className="flex flex-col gap-5 md:flex-row md:items-end md:justify-between">
      <div className="max-w-3xl">
        {eyebrow ? (
          <div className="mb-3 text-xs font-semibold uppercase tracking-[0.28em] text-[var(--accent-strong)]">
            {eyebrow}
          </div>
        ) : null}
        <h2 className="text-[2rem] font-semibold tracking-[-0.04em] text-slate-950">{title}</h2>
        {description ? <p className="mt-3 max-w-2xl text-sm leading-7 text-slate-600">{description}</p> : null}
      </div>
      {actions ? <div className="md:pb-1">{actions}</div> : null}
    </div>
  );
}
