import { StatusPill } from "@/components/StatusPill";
import { KpiCard } from "@/components/KpiCard";
import type { DashboardData } from "@/lib/types";

export function KpiGrid({ kpis }: { kpis: DashboardData["kpis"] }) {
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
      <KpiCard
        label="Last run"
        value={
          <span className="inline-flex items-center gap-2">
            <StatusPill status={kpis.lastRunStatus} />
            <span className="font-mono text-data-mono text-base">{kpis.lastRunIsoWeek}</span>
          </span>
        }
      />
      <KpiCard
        label="Reviews analyzed"
        value={kpis.reviewsAnalyzed?.toLocaleString() ?? "—"}
        subtext="10-week rolling window"
      />
      <KpiCard label="Themes found" value={kpis.themesFound ?? "—"} subtext="Top clusters summarized" />
      <KpiCard label="Next scheduled run" value={kpis.nextScheduledRun} subtext="GitHub Actions cron" />
    </div>
  );
}
