import type { RunStatus } from "@/lib/types";

const styles: Record<RunStatus, string> = {
  completed: "bg-status-completed-bg text-status-completed-text border-status-completed-border",
  failed: "bg-status-failed-bg text-status-failed-text border-status-failed-border",
  partial: "bg-status-partial-bg text-status-partial-text border-status-partial-border",
  skipped: "bg-status-skipped-bg text-status-skipped-text border-status-skipped-border",
  running: "bg-status-running-bg text-status-running-text border-status-running-border",
  pending: "bg-status-skipped-bg text-status-skipped-text border-status-skipped-border",
};

const labels: Record<RunStatus, string> = {
  completed: "Completed",
  failed: "Failed",
  partial: "Partial",
  skipped: "Skipped",
  running: "Running",
  pending: "Pending",
};

export function StatusPill({ status }: { status: RunStatus }) {
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-label-caps uppercase ${styles[status]}`}
    >
      {labels[status]}
    </span>
  );
}
