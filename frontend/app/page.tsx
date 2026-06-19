import { AlertBanner } from "@/components/AlertBanner";
import { DashboardFooter } from "@/components/DashboardFooter";
import { DashboardHeader } from "@/components/DashboardHeader";
import { KpiGrid } from "@/components/KpiGrid";
import { RunsTable } from "@/components/RunsTable";
import { Sidebar } from "@/components/Sidebar";
import { TopBar } from "@/components/TopBar";
import { loadDashboardData } from "@/lib/dashboard-data";

export const dynamic = "force-dynamic";

export default async function DashboardPage() {
  const data = await loadDashboardData();

  return (
    <div className="min-h-screen bg-surface">
      <Sidebar />
      <div className="pl-60">
        <TopBar product={data.product} environment={data.environment} />
        <main className="mx-auto max-w-container px-8 py-6">
          <div className="space-y-6">
            <DashboardHeader
              currentIsoWeek={data.currentIsoWeek}
              isoWeekPolicy={data.isoWeekPolicy}
              lastRunStatus={data.kpis.lastRunStatus}
              lastRunIsoWeek={data.kpis.lastRunIsoWeek}
            />

            {data.alert && <AlertBanner alert={data.alert} />}

            <KpiGrid kpis={data.kpis} />

            <RunsTable runs={data.runs} />

            <DashboardFooter note={data.schedulerNote} />
          </div>
        </main>
      </div>
    </div>
  );
}
