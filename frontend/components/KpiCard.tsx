import type { ReactNode } from "react";

interface KpiCardProps {
  label: string;
  value: ReactNode;
  subtext?: string;
}

export function KpiCard({ label, value, subtext }: KpiCardProps) {
  return (
    <div className="rounded border border-outline-variant bg-white px-4 py-3">
      <p className="text-label-caps uppercase text-on-surface-variant">{label}</p>
      <div className="mt-2 text-headline-lg text-on-surface">{value}</div>
      {subtext && <p className="mt-1 text-body-sm text-on-surface-variant">{subtext}</p>}
    </div>
  );
}
