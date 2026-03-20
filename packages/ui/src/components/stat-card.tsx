import { Card } from "./card";

export function StatCard({
  label,
  value,
  hint,
}: {
  label: string;
  value: string | number;
  hint?: string;
}) {
  return (
    <Card className="lift-hover p-5 md:p-6">
      <div className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">{label}</div>
      <div className="mt-4 text-[2rem] font-semibold tracking-[-0.04em] text-slate-950">{value}</div>
      {hint ? <div className="mt-3 text-xs leading-6 text-slate-500">{hint}</div> : null}
    </Card>
  );
}
