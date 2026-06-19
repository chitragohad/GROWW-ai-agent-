export type RunStatus = "completed" | "failed" | "partial" | "skipped" | "running" | "pending";

export interface RunRow {
  isoWeek: string;
  status: RunStatus;
  reviewCount: number | null;
  themeCount: number | null;
  durationSeconds: number | null;
  runId: string | null;
  docUrl: string | null;
  docStatus: "open" | "skipped" | "failed" | "none";
  emailStatus: "sent" | "draft" | "failed" | "skipped" | "none";
  errorMessage?: string | null;
}

export interface DashboardAlert {
  severity: "warning" | "error";
  message: string;
  isoWeek?: string;
}

export interface DashboardData {
  product: string;
  environment: "development" | "staging" | "production";
  currentIsoWeek: string;
  isoWeekPolicy: string;
  kpis: {
    lastRunStatus: RunStatus;
    lastRunIsoWeek: string;
    reviewsAnalyzed: number | null;
    themesFound: number | null;
    nextScheduledRun: string;
  };
  alert: DashboardAlert | null;
  runs: RunRow[];
  schedulerNote: string;
}
