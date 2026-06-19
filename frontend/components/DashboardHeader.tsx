import { Play, RefreshCw, TestTube2 } from "lucide-react";

import type { DashboardData } from "@/lib/types";

import { StatusPill } from "./StatusPill";

interface DashboardHeaderProps {
  currentIsoWeek: string;
  isoWeekPolicy: string;
  lastRunStatus: DashboardData["kpis"]["lastRunStatus"];
  lastRunIsoWeek: string;
}

export function DashboardHeader({
  currentIsoWeek,
  isoWeekPolicy,
  lastRunStatus,
  lastRunIsoWeek,
}: DashboardHeaderProps) {
  return (
    <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
      <div>
        <h1 className="text-headline-lg text-on-surface">Operator Dashboard</h1>
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <span className="rounded border border-outline-variant bg-white px-2.5 py-1 font-mono text-data-mono text-on-surface">
            {currentIsoWeek}
          </span>
          <span className="text-body-sm text-on-surface-variant">{isoWeekPolicy}</span>
        </div>
        <p className="mt-2 text-body-sm text-on-surface-variant">
          Last completed target week:{" "}
          <span className="font-mono text-data-mono text-on-surface">{lastRunIsoWeek}</span>{" "}
          <StatusPill status={lastRunStatus} />
        </p>
      </div>

      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          className="inline-flex items-center gap-2 rounded border border-primary bg-primary px-3 py-2 text-body-sm font-medium text-white hover:bg-primary/90"
        >
          <Play className="h-4 w-4" />
          Run now
        </button>
        <button
          type="button"
          className="inline-flex items-center gap-2 rounded border border-outline-variant bg-white px-3 py-2 text-body-sm font-medium text-on-surface hover:bg-surface-container-low"
        >
          <TestTube2 className="h-4 w-4" />
          Dry run
        </button>
        <button
          type="button"
          className="inline-flex items-center gap-2 rounded border border-outline-variant bg-white px-3 py-2 text-body-sm font-medium text-on-surface hover:bg-surface-container-low"
        >
          <RefreshCw className="h-4 w-4" />
          Backfill
        </button>
      </div>
    </div>
  );
}
