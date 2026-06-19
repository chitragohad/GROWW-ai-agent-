import { AlertTriangle, XCircle } from "lucide-react";

import type { DashboardAlert } from "@/lib/types";

export function AlertBanner({ alert }: { alert: DashboardAlert }) {
  const isError = alert.severity === "error";
  const border = isError ? "border-status-failed-border" : "border-status-partial-border";
  const accent = isError ? "bg-status-failed-text" : "bg-status-partial-text";
  const bg = isError ? "bg-status-failed-bg" : "bg-status-partial-bg";
  const text = isError ? "text-status-failed-text" : "text-status-partial-text";
  const Icon = isError ? XCircle : AlertTriangle;

  return (
    <div
      className={`relative overflow-hidden rounded border ${border} ${bg} px-4 py-3 pl-5`}
      role="alert"
    >
      <div className={`absolute inset-y-0 left-0 w-[3px] ${accent}`} />
      <div className={`flex items-start gap-2 ${text}`}>
        <Icon className="mt-0.5 h-4 w-4 shrink-0" />
        <div>
          <p className="text-body-sm font-medium">{alert.message}</p>
          {alert.isoWeek && (
            <p className="mt-0.5 font-mono text-data-mono opacity-80">ISO week {alert.isoWeek}</p>
          )}
        </div>
      </div>
    </div>
  );
}
