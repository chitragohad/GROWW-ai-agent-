"""End-to-end run orchestrator: ingest → analyze → render → MCP delivery (Phase 7)."""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, Literal, Optional

from pulse.agent.doc_delivery import deliver_doc_section
from pulse.agent.email_delivery import deliver_email_teaser
from pulse.agent.mcp_client import GoogleMcpClient, McpClientError
from pulse.agent.models import DocDeliveryResult, EmailDeliveryResult
from pulse.config import PulseConfig, load_pulse_config
from pulse.ingestion.service import IngestionResult, run_ingestion
from pulse.ledger.models import RunRecord
from pulse.ledger.store import LedgerStore, default_ledger_path
from pulse.logging import log_event
from pulse.models.report import _groq_payload
from pulse.monitoring.alerts import classify_run_record, emit_run_alert
from pulse.pipeline.service import AnalysisError, run_analysis_from_cache
from pulse.render.preview import render_report, write_preview_artifacts

logger = logging.getLogger(__name__)


class OrchestratorError(Exception):
    pass


@dataclass
class RunResult:
    run_id: str
    product: str
    iso_week: str
    status: Literal["completed", "failed", "skipped"]
    skipped: bool = False
    dry_run: bool = False
    run_dir: Optional[Path] = None
    doc_delivery: Optional[DocDeliveryResult] = None
    email_delivery: Optional[EmailDeliveryResult] = None
    error_message: Optional[str] = None
    ledger_record: Optional[RunRecord] = None
    stage_durations: Dict[str, float] = field(default_factory=dict)
    groq_metrics: Optional[dict] = None


def resolve_google_doc_id(config: PulseConfig) -> str:
    env_id = os.environ.get("GOOGLE_DOC_ID", "").strip()
    if env_id:
        return env_id
    doc_id = config.product.delivery.google_doc_id.strip()
    if not doc_id or doc_id.startswith("<"):
        raise OrchestratorError(
            "Google Doc ID not configured — set GOOGLE_DOC_ID env or delivery.google_doc_id in product config"
        )
    return doc_id


def resolve_email_recipients(config: PulseConfig) -> list[str]:
    env_recipients = os.environ.get("PULSE_EMAIL_RECIPIENTS", "").strip()
    if env_recipients:
        return [r.strip() for r in env_recipients.split(",") if r.strip()]
    return list(config.product.delivery.email.recipients)


def resolve_email_mode(
    config: PulseConfig,
    override: Optional[Literal["draft", "send"]] = None,
    *,
    production_confirmed: bool = False,
) -> Literal["draft", "send"]:
    if override:
        mode = override
    elif config.settings.pulse_email_mode:
        mode = config.settings.pulse_email_mode  # type: ignore[assignment]
    elif config.settings.pulse_env == "production":
        mode = config.product.delivery.email.default_mode
    else:
        mode = "draft"

    _validate_production_send(config, mode, production_confirmed=production_confirmed)
    return mode  # type: ignore[return-value]


def _validate_production_send(
    config: PulseConfig,
    mode: Literal["draft", "send"],
    *,
    production_confirmed: bool,
) -> None:
    if config.settings.pulse_env != "production" or mode != "send":
        return
    if config.settings.pulse_production_confirmed or production_confirmed:
        return
    raise OrchestratorError(
        "Production email send blocked — set PULSE_PRODUCTION_CONFIRM=1 or pass --confirm-production-send"
    )


def _default_run_id(iso_week: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{iso_week}-{stamp}-{uuid.uuid4().hex[:8]}"


def write_audit_record(
    run_dir: Path,
    *,
    run_id: str,
    product: str,
    iso_week: str,
    review_count: int,
    window_weeks: int,
    started_at: datetime,
    completed_at: Optional[datetime],
    status: str,
    doc_delivery: Optional[DocDeliveryResult] = None,
    email_delivery: Optional[EmailDeliveryResult] = None,
    dry_run: bool = False,
    error_message: Optional[str] = None,
    metrics: Optional[dict] = None,
) -> Path:
    payload: dict = {
        "run_id": run_id,
        "product": product,
        "iso_week": iso_week,
        "review_count": review_count,
        "window_weeks": window_weeks,
        "started_at": started_at.isoformat(),
        "completed_at": completed_at.isoformat() if completed_at else None,
        "status": status,
        "dry_run": dry_run,
    }
    if error_message:
        payload["error_message"] = error_message
    if metrics:
        payload["metrics"] = metrics
    if doc_delivery:
        payload["doc_delivery"] = {
            "document_id": doc_delivery.document_id,
            "section_anchor": doc_delivery.anchor,
            "url": doc_delivery.url,
            "appended": doc_delivery.appended,
            "skipped_duplicate": doc_delivery.skipped_duplicate,
        }
    if email_delivery:
        payload["email_delivery"] = {
            "mode": email_delivery.mode,
            "idempotency_key": email_delivery.idempotency_key,
            "draft_id": email_delivery.draft_id,
            "message_id": email_delivery.message_id,
            "recipients": email_delivery.recipients,
            "draft_created": email_delivery.draft_created,
            "skipped_duplicate": email_delivery.skipped_duplicate,
        }
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / "audit.json"
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
    return path


def run_pulse(
    product: str,
    *,
    iso_week: str,
    dry_run: bool = False,
    force_refresh: bool = False,
    email_mode: Optional[Literal["draft", "send"]] = None,
    production_confirmed: bool = False,
    config: Optional[PulseConfig] = None,
    ledger: Optional[LedgerStore] = None,
    mcp_client: Optional[GoogleMcpClient] = None,
    ingest_fn: Callable[..., IngestionResult] = run_ingestion,
    analyze_fn: Callable[..., tuple] = run_analysis_from_cache,
) -> RunResult:
    """
    Execute the full pulse pipeline for a product and ISO week.

    Skips entirely when the ledger already has a completed run for the week.
    On partial failure (Doc ok, Gmail fail), a retry skips Doc via anchor idempotency.
    """
    config = config or load_pulse_config(product)
    data_dir = config.settings.pulse_data_dir
    ledger = ledger or LedgerStore(default_ledger_path(data_dir))

    completed = ledger.find_completed_run(product, iso_week)
    if completed:
        log_event(
            logger,
            "pulse run skipped — already completed",
            run_id=completed.run_id,
            product=product,
            iso_week=iso_week,
            stage="orchestrator",
        )
        return RunResult(
            run_id=completed.run_id,
            product=product,
            iso_week=iso_week,
            status="skipped",
            skipped=True,
            dry_run=dry_run,
            ledger_record=completed,
        )

    partial = ledger.find_partial_delivery_run(product, iso_week)
    run_id = partial.run_id if partial else _default_run_id(iso_week)
    started_at = datetime.now(timezone.utc)

    if partial:
        ledger.reopen_run(run_id)
        log_event(
            logger,
            "pulse run resuming after partial failure (Gmail retry)",
            run_id=run_id,
            product=product,
            iso_week=iso_week,
            stage="orchestrator",
        )
    else:
        ledger.create_run(
            run_id,
            product,
            iso_week,
            window_weeks=config.product.ingestion.window_weeks,
        )

    run_dir: Optional[Path] = None
    review_count = 0
    window_weeks = config.product.ingestion.window_weeks
    doc_result: Optional[DocDeliveryResult] = None
    email_result: Optional[EmailDeliveryResult] = None
    stage_durations: Dict[str, float] = {}
    groq_metrics: Optional[dict] = None

    def _record_stage(stage: str, started: float) -> None:
        duration = round(time.perf_counter() - started, 3)
        stage_durations[stage] = duration
        log_event(
            logger,
            f"stage completed: {stage}",
            run_id=run_id,
            product=product,
            iso_week=iso_week,
            stage=stage,
            context={"duration_seconds": duration},
        )

    try:
        t0 = time.perf_counter()
        ingest_result = ingest_fn(
            product,
            force_refresh=force_refresh,
            data_dir=data_dir,
        )
        _record_stage("ingestion", t0)
        review_count = len(ingest_result.normalized_reviews)
        window_weeks = ingest_result.manifest.window_weeks

        if review_count < config.product.ingestion.min_reviews:
            raise OrchestratorError(
                f"Insufficient reviews: {review_count} < {config.product.ingestion.min_reviews}"
            )

        ledger.update_run_metrics(run_id, review_count=review_count, window_weeks=window_weeks)

        t0 = time.perf_counter()
        report, analysis, run_dir = analyze_fn(
            product,
            iso_week=iso_week,
            config=config,
            run_id=run_id,
        )
        _record_stage("analysis", t0)
        groq_metrics = _groq_payload(analysis.groq_usage) or None
        if groq_metrics:
            log_event(
                logger,
                "groq usage summary",
                run_id=run_id,
                product=product,
                iso_week=iso_week,
                stage="analysis",
                context=groq_metrics,
            )
        if run_dir is None:
            raise OrchestratorError("Analysis did not produce a run directory")

        rendered = render_report(report)
        t0 = time.perf_counter()
        write_preview_artifacts(rendered, run_dir)
        _record_stage("render", t0)

        metrics_payload = {
            "stage_durations_seconds": stage_durations,
            "groq": groq_metrics or {},
        }

        if dry_run:
            completed_at = datetime.now(timezone.utc)
            stage_durations["total"] = round((completed_at - started_at).total_seconds(), 3)
            metrics_payload["stage_durations_seconds"] = stage_durations
            write_audit_record(
                run_dir,
                run_id=run_id,
                product=product,
                iso_week=iso_week,
                review_count=review_count,
                window_weeks=window_weeks,
                started_at=started_at,
                completed_at=completed_at,
                status="completed",
                dry_run=True,
                metrics=metrics_payload,
            )
            record = ledger.mark_completed(run_id)
            log_event(
                logger,
                "pulse dry-run completed",
                run_id=run_id,
                product=product,
                iso_week=iso_week,
                stage="orchestrator",
                context={"stage_durations_seconds": stage_durations, "groq": groq_metrics or {}},
            )
            return RunResult(
                run_id=run_id,
                product=product,
                iso_week=iso_week,
                status="completed",
                dry_run=True,
                run_dir=run_dir,
                ledger_record=record,
                stage_durations=stage_durations,
                groq_metrics=groq_metrics,
            )

        doc_id = resolve_google_doc_id(config)
        recipients = resolve_email_recipients(config)
        if not recipients:
            raise OrchestratorError("No email recipients configured")

        email_mode = resolve_email_mode(
            config,
            email_mode,
            production_confirmed=production_confirmed,
        )
        client = mcp_client or GoogleMcpClient(
            config.settings.mcp_server_url,
            approval_key=config.settings.mcp_approval_key,
        )

        t0 = time.perf_counter()
        doc_result = deliver_doc_section(
            rendered.doc_section,
            doc_id,
            client=client,
            data_dir=data_dir,
            dry_run=False,
        )
        _record_stage("doc_delivery", t0)
        ledger.add_delivery(
            run_id,
            channel="google_doc",
            external_id=doc_result.anchor,
            url=doc_result.url,
            idempotency_key=doc_result.anchor,
        )

        rendered_with_link = render_report(report, doc_url=doc_result.url)
        t0 = time.perf_counter()
        email_result = deliver_email_teaser(
            rendered_with_link.email_teaser,
            recipients,
            client=client,
            data_dir=data_dir,
            mode=email_mode,
            dry_run=False,
        )
        _record_stage("email_delivery", t0)
        ledger.add_delivery(
            run_id,
            channel="gmail",
            external_id=email_result.draft_id or email_result.message_id or email_result.idempotency_key,
            url=email_result.doc_url,
            idempotency_key=email_result.idempotency_key,
        )

        completed_at = datetime.now(timezone.utc)
        stage_durations["total"] = round((completed_at - started_at).total_seconds(), 3)
        metrics_payload["stage_durations_seconds"] = stage_durations
        write_audit_record(
            run_dir,
            run_id=run_id,
            product=product,
            iso_week=iso_week,
            review_count=review_count,
            window_weeks=window_weeks,
            started_at=started_at,
            completed_at=completed_at,
            status="completed",
            doc_delivery=doc_result,
            email_delivery=email_result,
            metrics=metrics_payload,
        )
        record = ledger.mark_completed(run_id)
        log_event(
            logger,
            "pulse run completed",
            run_id=run_id,
            product=product,
            iso_week=iso_week,
            stage="orchestrator",
            context={"stage_durations_seconds": stage_durations, "groq": groq_metrics or {}},
        )
        return RunResult(
            run_id=run_id,
            product=product,
            iso_week=iso_week,
            status="completed",
            run_dir=run_dir,
            doc_delivery=doc_result,
            email_delivery=email_result,
            ledger_record=record,
            stage_durations=stage_durations,
            groq_metrics=groq_metrics,
        )

    except (OrchestratorError, AnalysisError, McpClientError, ValueError) as exc:
        error_message = str(exc)
        if run_dir:
            metrics_payload = {
                "stage_durations_seconds": stage_durations,
                "groq": groq_metrics or {},
            }
            write_audit_record(
                run_dir,
                run_id=run_id,
                product=product,
                iso_week=iso_week,
                review_count=review_count,
                window_weeks=window_weeks,
                started_at=started_at,
                completed_at=datetime.now(timezone.utc),
                status="failed",
                doc_delivery=doc_result,
                email_delivery=email_result,
                error_message=error_message,
                metrics=metrics_payload,
            )
        record = ledger.mark_failed(run_id, error_message)
        alert = classify_run_record(record)
        if alert:
            emit_run_alert(alert, webhook_url=config.settings.pulse_alert_webhook_url)
        log_event(
            logger,
            "pulse run failed",
            run_id=run_id,
            product=product,
            iso_week=iso_week,
            stage="orchestrator",
            context={"error": error_message, "stage_durations_seconds": stage_durations},
        )
        return RunResult(
            run_id=run_id,
            product=product,
            iso_week=iso_week,
            status="failed",
            run_dir=run_dir,
            doc_delivery=doc_result,
            email_delivery=email_result,
            error_message=error_message,
            ledger_record=record,
            stage_durations=stage_durations,
            groq_metrics=groq_metrics,
        )
    except Exception as exc:
        error_message = str(exc)
        ledger.mark_failed(run_id, error_message)
        log_event(
            logger,
            "pulse run failed",
            run_id=run_id,
            product=product,
            iso_week=iso_week,
            stage="orchestrator",
            context={"error": error_message},
        )
        raise
