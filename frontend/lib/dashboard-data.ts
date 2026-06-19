import fs from "fs";
import path from "path";

import { demoDashboard } from "./demo-data";
import { apiBaseUrl, isProductionDeploy } from "./env";
import type { DashboardData, RunRow, RunStatus } from "./types";

async function fetchFromPythonApi(): Promise<DashboardData | null> {
  try {
    const response = await fetch(`${apiBaseUrl()}/api/dashboard`, {
      cache: "no-store",
      next: { revalidate: 0 },
    });
    if (!response.ok) return null;
    return (await response.json()) as DashboardData;
  } catch {
    return null;
  }
}

function unavailableDashboard(message: string): DashboardData {
  return {
    ...demoDashboard,
    environment: "production",
    alert: { severity: "error", message },
    runs: [],
    kpis: {
      lastRunStatus: "pending",
      lastRunIsoWeek: demoDashboard.currentIsoWeek,
      reviewsAnalyzed: null,
      themesFound: null,
      nextScheduledRun: "Mon 09:00 IST",
    },
  };
}

function dataDir(): string {
  return process.env.PULSE_DATA_DIR ?? path.join(process.cwd(), "..", "data");
}

function readJson<T>(filePath: string): T | null {
  try {
    if (!fs.existsSync(filePath)) return null;
    return JSON.parse(fs.readFileSync(filePath, "utf-8")) as T;
  } catch {
    return null;
  }
}

function formatDuration(seconds: number | null | undefined): number | null {
  if (seconds == null || Number.isNaN(seconds)) return null;
  return Math.round(seconds);
}

function inferStatusFromAudit(audit: Record<string, unknown>): RunStatus {
  const status = audit.status as string | undefined;
  if (status === "completed") return "completed";
  if (status === "failed") {
    const doc = audit.doc_delivery as Record<string, unknown> | undefined;
    const email = audit.email_delivery as Record<string, unknown> | undefined;
    if (doc && !email) return "partial";
    return "failed";
  }
  return "pending";
}

function loadRunsFromFilesystem(): RunRow[] {
  const runsRoot = path.join(dataDir(), "runs");
  if (!fs.existsSync(runsRoot)) return [];

  const rows: RunRow[] = [];
  for (const runId of fs.readdirSync(runsRoot)) {
    const runDir = path.join(runsRoot, runId);
    if (!fs.statSync(runDir).isDirectory()) continue;

    const report = readJson<{ report?: { iso_week?: string; review_count?: number; themes?: unknown[] } }>(
      path.join(runDir, "report.json"),
    );
    const audit = readJson<Record<string, unknown>>(path.join(runDir, "audit.json"));
    if (!report?.report?.iso_week) continue;

    const isoWeek = report.report.iso_week;
    const docDelivery = audit?.doc_delivery as { url?: string } | undefined;
    const emailDelivery = audit?.email_delivery as { draft_created?: boolean } | undefined;
    const metrics = audit?.metrics as { stage_durations_seconds?: { total?: number } } | undefined;

    let status: RunStatus = audit ? inferStatusFromAudit(audit) : "completed";
    const anchors = readJson<Record<string, { url?: string }>>(path.join(dataDir(), "deliveries", "doc_anchors.json"));
    const anchorKey = `groww-${isoWeek}`;
    const docUrl = docDelivery?.url ?? anchors?.[anchorKey]?.url ?? null;

    if (!audit && docUrl) status = "completed";

    rows.push({
      isoWeek,
      status,
      reviewCount: report.report.review_count ?? null,
      themeCount: report.report.themes?.length ?? null,
      durationSeconds: formatDuration(metrics?.stage_durations_seconds?.total ?? null),
      runId,
      docUrl,
      docStatus: docUrl ? "open" : status === "skipped" ? "skipped" : "none",
      emailStatus: emailDelivery?.draft_created ? "draft" : docUrl ? "sent" : "none",
      errorMessage: (audit?.error_message as string | undefined) ?? null,
    });
  }

  return rows.sort((a, b) => b.isoWeek.localeCompare(a.isoWeek));
}

function mergeWithDemo(filesystemRuns: RunRow[]): RunRow[] {
  if (filesystemRuns.length === 0) return demoDashboard.runs;

  const byWeek = new Map<string, RunRow>();
  for (const row of demoDashboard.runs) {
    byWeek.set(row.isoWeek, row);
  }
  for (const row of filesystemRuns) {
    byWeek.set(row.isoWeek, { ...byWeek.get(row.isoWeek), ...row } as RunRow);
  }
  return Array.from(byWeek.values()).sort((a, b) => b.isoWeek.localeCompare(a.isoWeek));
}

export async function loadDashboardData(): Promise<DashboardData> {
  const fromApi = await fetchFromPythonApi();
  if (fromApi) return fromApi;

  if (isProductionDeploy()) {
    return unavailableDashboard(
      `Cannot reach Pulse API at ${apiBaseUrl()}. Set PULSE_API_URL on Vercel to your Railway API URL.`,
    );
  }

  const filesystemRuns = loadRunsFromFilesystem();
  const runs = mergeWithDemo(filesystemRuns);
  const latest = runs.find((r) => r.status === "completed" || r.reviewCount != null) ?? runs[0];
  const partial = runs.find((r) => r.status === "partial");

  const env = (process.env.PULSE_ENV ?? "development") as DashboardData["environment"];
  if (!["development", "staging", "production"].includes(env)) {
    return { ...demoDashboard, runs };
  }

  return {
    ...demoDashboard,
    environment: env,
    runs,
    kpis: {
      lastRunStatus: latest?.status ?? "pending",
      lastRunIsoWeek: latest?.isoWeek ?? demoDashboard.currentIsoWeek,
      reviewsAnalyzed: latest?.reviewCount ?? demoDashboard.kpis.reviewsAnalyzed,
      themesFound: latest?.themeCount ?? demoDashboard.kpis.themesFound,
      nextScheduledRun: demoDashboard.kpis.nextScheduledRun,
    },
    alert: partial
      ? {
          severity: "warning",
          message: "1 partial run — Doc delivered, Gmail failed. Retry available.",
          isoWeek: partial.isoWeek,
        }
      : runs.some((r) => r.status === "failed")
        ? {
            severity: "error",
            message: `${runs.filter((r) => r.status === "failed").length} failed run(s) in recent history.`,
          }
        : null,
  };
}
