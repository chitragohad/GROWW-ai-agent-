import { ExternalLink, RotateCcw } from "lucide-react";

import { StatusPill } from "@/components/StatusPill";
import type { RunRow } from "@/lib/types";

function DocCell({ row }: { row: RunRow }) {
  if (row.docStatus === "open" && row.docUrl) {
    return (
      <a
        href={row.docUrl}
        target="_blank"
        rel="noopener noreferrer"
        className="inline-flex items-center gap-1 text-body-sm text-on-surface hover:underline"
      >
        Open
        <ExternalLink className="h-3 w-3" />
      </a>
    );
  }
  if (row.docStatus === "skipped" || row.status === "skipped") return <span className="text-on-surface-variant">—</span>;
  if (row.docStatus === "failed") return <span className="text-status-failed-text">Failed</span>;
  return <span className="text-on-surface-variant">—</span>;
}

function EmailCell({ row }: { row: RunRow }) {
  if (row.emailStatus === "sent") return <span className="text-body-sm text-status-completed-text">Sent</span>;
  if (row.emailStatus === "draft") return <span className="text-body-sm text-on-surface">Draft</span>;
  if (row.emailStatus === "failed") return <span className="text-body-sm text-status-failed-text">Failed</span>;
  if (row.emailStatus === "skipped" || row.status === "skipped") return <span className="text-on-surface-variant">—</span>;
  return <span className="text-on-surface-variant">—</span>;
}

function formatDuration(seconds: number | null): string {
  if (seconds == null) return "—";
  return `${seconds}s`;
}

export function RunsTable({ runs }: { runs: RunRow[] }) {
  return (
    <div className="overflow-hidden rounded border border-outline-variant bg-white">
      <div className="border-b border-outline-variant px-4 py-3">
        <h2 className="text-headline-md text-on-surface">Recent runs</h2>
        <p className="text-body-sm text-on-surface-variant">Weekly pulse executions with delivery status</p>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[800px] border-collapse text-left">
          <thead>
            <tr className="border-b border-outline-variant bg-surface-container-low">
              {["ISO week", "Status", "Reviews", "Duration", "Doc", "Email", "Actions"].map((col) => (
                <th
                  key={col}
                  className="px-3 py-2.5 text-label-caps uppercase text-on-surface-variant first:pl-4 last:pr-4"
                >
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {runs.map((row) => (
              <tr
                key={row.isoWeek}
                className="group h-11 border-b border-outline-variant/70 last:border-b-0 hover:bg-surface-container-low"
              >
                <td className="px-3 py-2 pl-4 font-mono text-data-mono text-on-surface">{row.isoWeek}</td>
                <td className="px-3 py-2">
                  <StatusPill status={row.status} />
                </td>
                <td className="px-3 py-2 font-mono text-data-mono text-on-surface">
                  {row.reviewCount ?? "—"}
                </td>
                <td className="px-3 py-2 font-mono text-data-mono text-on-surface">
                  {formatDuration(row.durationSeconds)}
                </td>
                <td className="px-3 py-2">
                  <DocCell row={row} />
                </td>
                <td className="px-3 py-2">
                  <EmailCell row={row} />
                </td>
                <td className="px-3 py-2 pr-4">
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      className="text-body-sm font-medium text-on-surface hover:underline"
                    >
                      View
                    </button>
                    {row.status === "partial" && (
                      <button
                        type="button"
                        className="inline-flex items-center gap-1 text-body-sm font-medium text-status-partial-text hover:underline"
                      >
                        <RotateCcw className="h-3 w-3" />
                        Retry
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
