"""FastAPI backend for the Groww Pulse operator dashboard."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional

from pulse.config import load_pulse_config
from pulse.iso_week import resolve_default_iso_week
from pulse.ledger.store import LedgerStore, default_ledger_path
from pulse.monitoring.check import check_recent_failures

try:
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
except ImportError as exc:  # pragma: no cover
    raise ImportError("Install API deps: pip install -e '.[web]'") from exc


def _cors_origins() -> list[str]:
    origins = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]
    extra = os.environ.get("PULSE_CORS_ORIGINS", "").strip()
    if extra:
        origins.extend(part.strip() for part in extra.split(",") if part.strip())
    return origins


app = FastAPI(title="Groww Pulse API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _data_dir() -> Path:
    config = load_pulse_config("groww")
    return config.settings.pulse_data_dir


def _load_run_from_dir(run_dir: Path) -> Optional[dict[str, Any]]:
    report_path = run_dir / "report.json"
    audit_path = run_dir / "audit.json"
    if not report_path.is_file():
        return None

    report_payload = json.loads(report_path.read_text(encoding="utf-8"))
    report = report_payload.get("report", {})
    iso_week = report.get("iso_week")
    if not iso_week:
        return None

    audit = json.loads(audit_path.read_text(encoding="utf-8")) if audit_path.is_file() else None
    metrics = (audit or {}).get("metrics", {})
    durations = metrics.get("stage_durations_seconds", {})

    status = "completed"
    error_message = None
    doc_url = None
    email_status = "none"
    if audit:
        status = audit.get("status", "completed")
        error_message = audit.get("error_message")
        doc_delivery = audit.get("doc_delivery") or {}
        email_delivery = audit.get("email_delivery") or {}
        doc_url = doc_delivery.get("url")
        if status == "failed" and doc_delivery and not email_delivery:
            status = "partial"
        if email_delivery.get("draft_created"):
            email_status = "draft"
        elif email_delivery:
            email_status = "sent"
    else:
        anchors_path = _data_dir() / "deliveries" / "doc_anchors.json"
        if anchors_path.is_file():
            anchors = json.loads(anchors_path.read_text(encoding="utf-8"))
            anchor = anchors.get(f"groww-{iso_week}")
            if anchor:
                doc_url = anchor.get("url")
                email_status = "draft"

    return {
        "isoWeek": iso_week,
        "status": status,
        "reviewCount": report.get("review_count"),
        "themeCount": len(report.get("themes") or []),
        "durationSeconds": durations.get("total"),
        "runId": run_dir.name,
        "docUrl": doc_url,
        "docStatus": "open" if doc_url else "none",
        "emailStatus": email_status,
        "errorMessage": error_message,
    }


def _load_runs_from_ledger(product: str) -> list[dict[str, Any]]:
    config = load_pulse_config(product)
    ledger_path = default_ledger_path(config.settings.pulse_data_dir)
    if not ledger_path.is_file():
        return []

    ledger = LedgerStore(ledger_path)
    rows: list[dict[str, Any]] = []
    for record in ledger.list_recent_runs(product, limit=20):
        doc = next((d for d in record.deliveries if d.channel == "google_doc"), None)
        gmail = next((d for d in record.deliveries if d.channel == "gmail"), None)
        status = record.status
        if status == "failed" and doc and not gmail:
            status = "partial"
        rows.append(
            {
                "isoWeek": record.iso_week,
                "status": status,
                "reviewCount": record.review_count,
                "themeCount": None,
                "durationSeconds": None,
                "runId": record.run_id,
                "docUrl": doc.url if doc else None,
                "docStatus": "open" if doc else "none",
                "emailStatus": "sent" if gmail else ("failed" if status == "partial" else "none"),
                "errorMessage": record.error_message,
            }
        )
    return rows


def _demo_runs() -> list[dict[str, Any]]:
    if os.environ.get("PULSE_ENV") == "production":
        return []
    return [
        {
            "isoWeek": "2026-W24",
            "status": "completed",
            "reviewCount": 884,
            "themeCount": 5,
            "durationSeconds": 48,
            "runId": "2026-W24-20260610T132614Z-5c9efbc2",
            "docUrl": "https://docs.google.com/document/d/1ArysoTqwaheaUsz4QLHdm5HKOvkkAe_aDwbVnz43ZfA/edit",
            "docStatus": "open",
            "emailStatus": "draft",
        },
        {
            "isoWeek": "2026-W23",
            "status": "skipped",
            "reviewCount": None,
            "themeCount": None,
            "durationSeconds": None,
            "runId": None,
            "docUrl": None,
            "docStatus": "none",
            "emailStatus": "none",
        },
        {
            "isoWeek": "2026-W22",
            "status": "partial",
            "reviewCount": 872,
            "themeCount": 5,
            "durationSeconds": 41,
            "runId": "2026-W22-demo",
            "docUrl": "https://docs.google.com/document/d/1ArysoTqwaheaUsz4QLHdm5HKOvkkAe_aDwbVnz43ZfA/edit",
            "docStatus": "open",
            "emailStatus": "failed",
            "errorMessage": "Gmail MCP unavailable",
        },
    ]


def build_dashboard_payload() -> dict[str, Any]:
    config = load_pulse_config("groww")
    data_dir = config.settings.pulse_data_dir
    runs_root = data_dir / "runs"

    filesystem_runs: list[dict[str, Any]] = []
    if runs_root.is_dir():
        for child in sorted(runs_root.iterdir(), reverse=True):
            if child.is_dir():
                row = _load_run_from_dir(child)
                if row:
                    filesystem_runs.append(row)

    ledger_runs = _load_runs_from_ledger("groww")
    by_week = {row["isoWeek"]: row for row in _demo_runs()}
    for row in ledger_runs + filesystem_runs:
        by_week[row["isoWeek"]] = {**by_week.get(row["isoWeek"], {}), **row}

    runs = sorted(by_week.values(), key=lambda r: r["isoWeek"], reverse=True)
    latest = next((r for r in runs if r.get("reviewCount")), runs[0] if runs else None)
    partial = next((r for r in runs if r.get("status") == "partial"), None)
    failed_count = sum(1 for r in runs if r.get("status") == "failed")

    env = os.environ.get("PULSE_ENV", "development")
    if env not in ("development", "staging", "production"):
        env = "development"

    alert = None
    if partial:
        alert = {
            "severity": "warning",
            "message": "1 partial run — Doc delivered, Gmail failed. Retry available.",
            "isoWeek": partial["isoWeek"],
        }
    elif failed_count:
        alert = {
            "severity": "error",
            "message": f"{failed_count} failed run(s) in recent history.",
        }

    scheduler = (
        "Railway cron · Mon 09:00 IST · scripts/railway-weekly-pulse.sh"
        if env == "production"
        else "GitHub Actions · Mon 09:00 IST · .github/workflows/weekly-pulse.yml"
    )

    return {
        "product": config.product.display_name,
        "environment": env,
        "currentIsoWeek": resolve_default_iso_week(config.product.scheduling),
        "isoWeekPolicy": "Monday before 9am IST → previous complete week",
        "kpis": {
            "lastRunStatus": latest.get("status", "pending") if latest else "pending",
            "lastRunIsoWeek": latest.get("isoWeek", resolve_default_iso_week(config.product.scheduling))
            if latest
            else resolve_default_iso_week(config.product.scheduling),
            "reviewsAnalyzed": latest.get("reviewCount") if latest else None,
            "themesFound": latest.get("themeCount") if latest else None,
            "nextScheduledRun": "Mon 09:00 IST",
        },
        "alert": alert,
        "runs": runs,
        "schedulerNote": scheduler,
    }


@app.get("/")
def root() -> dict[str, Any]:
    """Landing page for Railway/public URL — avoids 404 on `/`."""
    return {
        "service": "groww-pulse-api",
        "status": "ok",
        "message": "Groww Weekly Review Pulse API. Use /api/dashboard for operator data.",
        "docs": "/docs",
        "endpoints": {
            "health": "/health",
            "dashboard": "/api/dashboard",
            "status": "/api/status/{iso_week}",
            "check_failures": "/api/check-failures",
        },
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "groww-pulse-api"}


@app.get("/api/dashboard")
def dashboard() -> dict[str, Any]:
    return build_dashboard_payload()


@app.get("/api/status/{iso_week}")
def status(iso_week: str) -> dict[str, Any]:
    config = load_pulse_config("groww")
    ledger = LedgerStore(default_ledger_path(config.settings.pulse_data_dir))
    record = ledger.find_latest_run("groww", iso_week)
    if record is None:
        return {"status": "not_found", "iso_week": iso_week}
    return {
        "run_id": record.run_id,
        "iso_week": record.iso_week,
        "status": record.status,
        "review_count": record.review_count,
        "error_message": record.error_message,
        "deliveries": [d.model_dump(mode="json") for d in record.deliveries],
    }


@app.get("/api/check-failures")
def check_failures(since_days: int = 7) -> dict[str, Any]:
    config = load_pulse_config("groww")
    ledger = LedgerStore(default_ledger_path(config.settings.pulse_data_dir))
    result = check_recent_failures("groww", ledger=ledger, since_days=since_days)
    return {
        "failed_count": result.failed_count,
        "partial_count": result.partial_count,
        "alerts": [
            {
                "severity": a.severity,
                "iso_week": a.iso_week,
                "run_id": a.run_id,
                "message": a.message,
            }
            for a in result.alerts
        ],
    }


def main() -> None:
    import uvicorn

    port = int(os.environ.get("PORT", os.environ.get("PULSE_API_PORT", "8001")))
    reload_enabled = os.environ.get("PULSE_ENV", "development") == "development"
    uvicorn.run(
        "pulse.api.server:app",
        host="0.0.0.0",
        port=port,
        reload=reload_enabled,
    )


if __name__ == "__main__":
    main()
