export function DashboardFooter({ note }: { note: string }) {
  return (
    <footer className="flex flex-wrap items-center justify-between gap-2 border-t border-outline-variant pt-4 text-body-sm text-on-surface-variant">
      <span>{note}</span>
      <div className="flex gap-4">
        <button type="button" className="hover:text-on-surface hover:underline">
          check-failures
        </button>
        <button type="button" className="cursor-not-allowed text-on-surface-variant/50">
          Settings (coming soon)
        </button>
      </div>
    </footer>
  );
}
