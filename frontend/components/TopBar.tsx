import type { DashboardData } from "@/lib/types";

const envStyles: Record<DashboardData["environment"], string> = {
  development: "bg-surface-container text-on-surface-variant border-outline-variant",
  staging: "bg-status-partial-bg text-status-partial-text border-status-partial-border",
  production: "bg-primary text-white border-primary",
};

export function TopBar({ product, environment }: Pick<DashboardData, "product" | "environment">) {
  return (
    <header className="flex h-14 items-center justify-between border-b border-outline-variant bg-white px-6">
      <div className="flex items-center gap-3">
        <span className="text-body-sm text-on-surface-variant">Product</span>
        <span className="text-body-sm font-semibold text-on-surface">{product}</span>
        <span
          className={`rounded border px-2 py-0.5 text-label-caps uppercase ${envStyles[environment]}`}
        >
          {environment}
        </span>
      </div>

      <div className="flex items-center gap-3">
        <div className="flex h-8 w-8 items-center justify-center rounded-full border border-outline-variant bg-surface-container-low text-body-sm font-medium text-on-surface-variant">
          OP
        </div>
      </div>
    </header>
  );
}
