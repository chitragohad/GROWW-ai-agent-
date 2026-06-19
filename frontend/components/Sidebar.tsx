"use client";

import {
  Activity,
  CalendarClock,
  History,
  LayoutDashboard,
  Layers,
  Settings,
  Zap,
} from "lucide-react";

const navItems = [
  { label: "Dashboard", icon: LayoutDashboard, active: true, href: "/" },
  { label: "Reports", icon: Layers, active: false, disabled: true },
  { label: "Run history", icon: History, active: false, disabled: true },
  { label: "Backfill", icon: CalendarClock, active: false, disabled: true },
  { label: "Monitoring", icon: Activity, active: false, disabled: true },
  { label: "Settings", icon: Settings, active: false, disabled: true },
];

export function Sidebar() {
  return (
    <aside className="fixed inset-y-0 left-0 z-20 flex w-60 flex-col border-r border-outline-variant bg-white">
      <div className="flex h-14 items-center gap-2 border-b border-outline-variant px-4">
        <div className="flex h-8 w-8 items-center justify-center rounded bg-primary text-white">
          <Zap className="h-4 w-4" />
        </div>
        <div>
          <p className="text-body-sm font-semibold text-on-surface">Review Pulse</p>
          <p className="text-[11px] text-on-surface-variant">Operator console</p>
        </div>
      </div>

      <nav className="flex-1 space-y-0.5 p-3">
        {navItems.map(({ label, icon: Icon, active, disabled }) => (
          <button
            key={label}
            type="button"
            disabled={disabled}
            className={[
              "flex w-full items-center gap-2.5 rounded px-3 py-2 text-body-sm transition-colors",
              active
                ? "bg-surface-container font-medium text-on-surface"
                : disabled
                  ? "cursor-not-allowed text-on-surface-variant/50"
                  : "text-on-surface-variant hover:bg-surface-container-low",
            ].join(" ")}
          >
            <Icon className="h-4 w-4 shrink-0" />
            {label}
            {disabled && label !== "Dashboard" && (
              <span className="ml-auto text-[10px] uppercase tracking-wide text-on-surface-variant/60">Soon</span>
            )}
          </button>
        ))}
      </nav>

      <div className="border-t border-outline-variant p-4">
        <p className="text-label-caps uppercase text-on-surface-variant">Product</p>
        <p className="mt-1 text-body-sm font-medium text-on-surface">Groww</p>
      </div>
    </aside>
  );
}
