"""Pulse CLI entry point."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import List, Optional

from pulse.agent.backfill import run_backfill
from pulse.agent.doc_delivery import deliver_doc_section
from pulse.agent.email_delivery import deliver_email_teaser
from pulse.agent.mcp_client import GoogleMcpClient, McpClientError
from pulse.agent.orchestrator import RunResult, run_pulse
from pulse.ledger.store import LedgerStore, default_ledger_path
from pulse.agent.run_loader import (
    doc_url_for_anchor,
    load_or_render_doc_section,
    load_or_render_email_teaser,
    load_report_from_run,
)
from pulse.render.anchors import section_anchor
from pulse.config import load_pulse_config
from pulse.ingestion.service import run_ingestion
from pulse.iso_week import resolve_iso_week
from pulse.logging import get_logger, log_event, setup_logging
from pulse.monitoring.check import check_recent_failures
from pulse.pipeline.service import AnalysisError, run_analysis_from_cache
from pulse.render.preview import render_report, write_preview_artifacts


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pulse",
        description="Groww Weekly Review Pulse — Play Store insights to Google Workspace",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run pulse for a product and ISO week")
    run_parser.add_argument("--product", default="groww", help="Product slug (default: groww)")
    run_parser.add_argument(
        "--iso-week",
        help="ISO 8601 week e.g. 2026-W23 (default: policy from product config)",
    )
    run_parser.add_argument("--dry-run", action="store_true", help="Skip MCP delivery writes")
    run_parser.add_argument(
        "--force-refresh",
        action="store_true",
        help="Re-scrape Play Store before analysis",
    )
    run_parser.add_argument(
        "--email-mode",
        choices=["draft", "send"],
        help="Override PULSE_EMAIL_MODE (draft only on hosted MCP today)",
    )
    run_parser.add_argument(
        "--confirm-production-send",
        action="store_true",
        help="Acknowledge production email send (required when PULSE_ENV=production and mode=send)",
    )

    dry_run_parser = subparsers.add_parser(
        "dry-run",
        help="Full pipeline without MCP writes (Phase 8)",
    )
    dry_run_parser.add_argument("--product", default="groww", help="Product slug (default: groww)")
    dry_run_parser.add_argument(
        "--iso-week",
        help="ISO 8601 week e.g. 2026-W23 (default: policy from product config)",
    )
    dry_run_parser.add_argument(
        "--force-refresh",
        action="store_true",
        help="Re-scrape Play Store before analysis",
    )

    backfill_parser = subparsers.add_parser(
        "backfill",
        help="Sequential ISO week runs with ledger idempotency (Phase 8)",
    )
    backfill_parser.add_argument("--product", default="groww", help="Product slug (default: groww)")
    backfill_parser.add_argument("--from", dest="from_week", required=True, help="Start ISO week e.g. 2026-W20")
    backfill_parser.add_argument("--to", dest="to_week", required=True, help="End ISO week e.g. 2026-W22")
    backfill_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Skip MCP delivery writes for every week",
    )
    backfill_parser.add_argument(
        "--force-refresh",
        action="store_true",
        help="Re-scrape Play Store on the first week only",
    )
    backfill_parser.add_argument(
        "--email-mode",
        choices=["draft", "send"],
        help="Override PULSE_EMAIL_MODE",
    )
    backfill_parser.add_argument(
        "--confirm-production-send",
        action="store_true",
        help="Acknowledge production email send",
    )

    check_failures_parser = subparsers.add_parser(
        "check-failures",
        help="List recent failed/partial runs from the ledger (Phase 9)",
    )
    check_failures_parser.add_argument("--product", default="groww", help="Product slug (default: groww)")
    check_failures_parser.add_argument(
        "--since-days",
        type=int,
        default=7,
        help="Look back N days for failed runs (default: 7)",
    )

    ingest_parser = subparsers.add_parser("ingest", help="Fetch and cache Play Store reviews")
    ingest_parser.add_argument("--product", default="groww", help="Product slug (default: groww)")
    ingest_parser.add_argument(
        "--weeks-back",
        type=int,
        help="Rolling review window in weeks (8–12; default from product config)",
    )
    ingest_parser.add_argument(
        "--force-refresh",
        action="store_true",
        help="Ignore cache and re-scrape Play Store",
    )

    analyze_parser = subparsers.add_parser(
        "analyze",
        help="Cluster and summarize cached reviews (Phase 2)",
    )
    analyze_parser.add_argument("--product", default="groww", help="Product slug (default: groww)")
    analyze_parser.add_argument(
        "--iso-week",
        help="ISO 8601 week e.g. 2026-W23 (default: current UTC week)",
    )
    analyze_parser.add_argument(
        "--cache-date",
        help="Cache folder date YYYY-MM-DD (default: latest)",
    )
    analyze_parser.add_argument(
        "--skip-llm",
        action="store_true",
        help="Run clustering only; skip Groq summarization",
    )
    analyze_parser.add_argument(
        "--run-id",
        help="Optional run id for report.json output",
    )

    deliver_doc_parser = subparsers.add_parser(
        "deliver-doc",
        help="Append rendered Doc section via hosted Google MCP (Phase 5)",
    )
    deliver_doc_parser.add_argument("--product", default="groww", help="Product slug (default: groww)")
    deliver_doc_parser.add_argument(
        "--run-dir",
        required=True,
        help="Path to data/runs/{run_id} containing report.json or doc_section.json",
    )
    deliver_doc_parser.add_argument(
        "--doc-id",
        help="Google Doc ID (default: delivery.google_doc_id from product config)",
    )
    deliver_doc_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Check idempotency and skip MCP append",
    )

    deliver_email_parser = subparsers.add_parser(
        "deliver-email",
        help="Create Gmail draft via hosted Google MCP (Phase 6)",
    )
    deliver_email_parser.add_argument("--product", default="groww", help="Product slug (default: groww)")
    deliver_email_parser.add_argument(
        "--run-dir",
        required=True,
        help="Path to data/runs/{run_id} containing report.json",
    )
    deliver_email_parser.add_argument(
        "--doc-url",
        help="Google Doc URL for CTA (default: from Phase 5 anchor ledger)",
    )
    deliver_email_parser.add_argument(
        "--to",
        action="append",
        dest="recipients",
        help="Recipient email (repeatable; default from product config)",
    )
    deliver_email_parser.add_argument(
        "--email-mode",
        choices=["draft", "send"],
        help="Override PULSE_EMAIL_MODE (draft only on hosted MCP today)",
    )
    deliver_email_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Check idempotency and skip MCP draft creation",
    )

    status_parser = subparsers.add_parser(
        "status",
        help="Show ledger status for a product and ISO week (Phase 7)",
    )
    status_parser.add_argument("--product", default="groww", help="Product slug (default: groww)")
    status_parser.add_argument(
        "--iso-week",
        required=True,
        help="ISO 8601 week e.g. 2026-W23",
    )

    return parser


def _run_result_summary(command: str, result: RunResult) -> dict:
    summary: dict = {
        "command": command,
        "product": result.product,
        "iso_week": result.iso_week,
        "run_id": result.run_id,
        "status": result.status,
        "skipped": result.skipped,
        "dry_run": result.dry_run,
        "run_dir": str(result.run_dir) if result.run_dir else None,
        "error_message": result.error_message,
    }
    if result.stage_durations:
        summary["stage_durations_seconds"] = result.stage_durations
    if result.groq_metrics:
        summary["groq"] = result.groq_metrics
    if result.doc_delivery:
        summary["doc_delivery"] = {
            "anchor": result.doc_delivery.anchor,
            "document_id": result.doc_delivery.document_id,
            "url": result.doc_delivery.url,
            "appended": result.doc_delivery.appended,
            "skipped_duplicate": result.doc_delivery.skipped_duplicate,
        }
    if result.email_delivery:
        summary["email_delivery"] = {
            "idempotency_key": result.email_delivery.idempotency_key,
            "draft_id": result.email_delivery.draft_id,
            "message_id": result.email_delivery.message_id,
            "draft_created": result.email_delivery.draft_created,
            "skipped_duplicate": result.email_delivery.skipped_duplicate,
        }
    if result.ledger_record and result.ledger_record.deliveries:
        summary["deliveries"] = [d.model_dump(mode="json") for d in result.ledger_record.deliveries]
    return summary


def _resolve_cli_iso_week(args: argparse.Namespace, config) -> str:
    return resolve_iso_week(getattr(args, "iso_week", None), config.product.scheduling)


def cmd_run(args: argparse.Namespace) -> int:
    setup_logging()
    logger = get_logger("pulse.cli")
    config = load_pulse_config(args.product)
    iso_week = _resolve_cli_iso_week(args, config)

    try:
        result = run_pulse(
            args.product,
            iso_week=iso_week,
            dry_run=args.dry_run,
            force_refresh=args.force_refresh,
            email_mode=args.email_mode,
            production_confirmed=args.confirm_production_send,
            config=config,
        )
    except Exception as exc:
        print(
            json.dumps(
                {
                    "command": "run",
                    "product": args.product,
                    "iso_week": iso_week,
                    "status": "error",
                    "message": str(exc),
                },
                indent=2,
            )
        )
        log_event(
            logger,
            "pulse run error",
            product=args.product,
            iso_week=iso_week,
            stage="cli",
            context={"error": str(exc)},
        )
        return 1

    summary = _run_result_summary("run", result)
    print(json.dumps(summary, indent=2))
    log_event(
        logger,
        "pulse run completed",
        run_id=result.run_id,
        product=result.product,
        iso_week=result.iso_week,
        stage="cli",
        context={
            "status": result.status,
            "skipped": result.skipped,
            "dry_run": result.dry_run,
            "stage_durations_seconds": result.stage_durations,
        },
    )
    if result.status == "failed":
        return 1
    return 0


def cmd_dry_run(args: argparse.Namespace) -> int:
    setup_logging()
    logger = get_logger("pulse.cli")
    config = load_pulse_config(args.product)
    iso_week = _resolve_cli_iso_week(args, config)

    try:
        result = run_pulse(
            args.product,
            iso_week=iso_week,
            dry_run=True,
            force_refresh=args.force_refresh,
            config=config,
        )
    except Exception as exc:
        print(
            json.dumps(
                {
                    "command": "dry-run",
                    "product": args.product,
                    "iso_week": iso_week,
                    "status": "error",
                    "message": str(exc),
                },
                indent=2,
            )
        )
        return 1

    summary = _run_result_summary("dry-run", result)
    print(json.dumps(summary, indent=2))
    log_event(
        logger,
        "pulse dry-run completed",
        run_id=result.run_id,
        product=result.product,
        iso_week=result.iso_week,
        stage="cli",
        context={"stage_durations_seconds": result.stage_durations},
    )
    if result.status == "failed":
        return 1
    return 0


def cmd_backfill(args: argparse.Namespace) -> int:
    setup_logging()
    logger = get_logger("pulse.cli")
    config = load_pulse_config(args.product)

    try:
        backfill = run_backfill(
            args.product,
            from_week=args.from_week,
            to_week=args.to_week,
            dry_run=args.dry_run,
            force_refresh=args.force_refresh,
            email_mode=args.email_mode,
            production_confirmed=args.confirm_production_send,
            config=config,
        )
    except ValueError as exc:
        print(
            json.dumps(
                {
                    "command": "backfill",
                    "product": args.product,
                    "status": "error",
                    "message": str(exc),
                },
                indent=2,
            )
        )
        return 2
    except Exception as exc:
        print(
            json.dumps(
                {
                    "command": "backfill",
                    "product": args.product,
                    "status": "error",
                    "message": str(exc),
                },
                indent=2,
            )
        )
        return 1

    summary = {
        "command": "backfill",
        "product": backfill.product,
        "from_week": backfill.from_week,
        "to_week": backfill.to_week,
        "week_count": len(backfill.weeks),
        "completed": backfill.completed_count,
        "skipped": backfill.skipped_count,
        "failed": backfill.failed_count,
        "dry_run": args.dry_run,
        "weeks": [_run_result_summary("backfill-week", r) for r in backfill.results],
    }
    print(json.dumps(summary, indent=2))
    log_event(
        logger,
        "pulse backfill completed",
        product=args.product,
        stage="cli",
        context={
            "completed": backfill.completed_count,
            "skipped": backfill.skipped_count,
            "failed": backfill.failed_count,
        },
    )
    if backfill.failed_count:
        return 1
    return 0


def cmd_check_failures(args: argparse.Namespace) -> int:
    setup_logging()
    config = load_pulse_config(args.product)
    ledger = LedgerStore(default_ledger_path(config.settings.pulse_data_dir))
    result = check_recent_failures(
        args.product,
        ledger=ledger,
        since_days=args.since_days,
    )

    summary = {
        "command": "check-failures",
        "product": result.product,
        "since": result.since.isoformat(),
        "since_days": args.since_days,
        "failed_count": result.failed_count,
        "partial_count": result.partial_count,
        "alerts": [
            {
                "severity": alert.severity,
                "iso_week": alert.iso_week,
                "run_id": alert.run_id,
                "message": alert.message,
                "error_message": alert.error_message,
            }
            for alert in result.alerts
        ],
    }
    print(json.dumps(summary, indent=2))
    if result.alerts:
        return 1
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    setup_logging()
    config = load_pulse_config(args.product)
    ledger = LedgerStore(default_ledger_path(config.settings.pulse_data_dir))
    record = ledger.find_latest_run(args.product, args.iso_week)

    if record is None:
        print(
            json.dumps(
                {
                    "command": "status",
                    "product": args.product,
                    "iso_week": args.iso_week,
                    "status": "not_found",
                    "message": "No run recorded for this product and ISO week",
                },
                indent=2,
            )
        )
        return 0

    summary = {
        "command": "status",
        "product": record.product,
        "iso_week": record.iso_week,
        "run_id": record.run_id,
        "status": record.status,
        "review_count": record.review_count,
        "window_weeks": record.window_weeks,
        "started_at": record.started_at.isoformat(),
        "completed_at": record.completed_at.isoformat() if record.completed_at else None,
        "error_message": record.error_message,
        "deliveries": [d.model_dump(mode="json") for d in record.deliveries],
    }
    print(json.dumps(summary, indent=2))
    return 0


def cmd_ingest(args: argparse.Namespace) -> int:
    setup_logging()
    logger = get_logger("pulse.cli")
    config = load_pulse_config(args.product)

    weeks_back = args.weeks_back or config.product.ingestion.window_weeks
    if weeks_back < 8 or weeks_back > 12:
        print(
            json.dumps(
                {
                    "command": "ingest",
                    "status": "error",
                    "message": f"weeks-back must be between 8 and 12, got {weeks_back}",
                },
                indent=2,
            )
        )
        return 2

    try:
        result = run_ingestion(
            args.product,
            weeks_back=weeks_back,
            force_refresh=args.force_refresh,
            data_dir=config.settings.pulse_data_dir,
        )
    except Exception as exc:
        print(
            json.dumps(
                {
                    "command": "ingest",
                    "product": args.product,
                    "status": "error",
                    "message": str(exc),
                },
                indent=2,
            )
        )
        log_event(
            logger,
            "pulse ingest failed",
            product=args.product,
            stage="cli",
            context={"error": str(exc)},
        )
        return 1

    manifest = result.manifest
    summary = {
        "command": "ingest",
        "product": result.product,
        "status": "success",
        "from_cache": manifest.from_cache,
        "package_id": manifest.package_id,
        "window_weeks": manifest.window_weeks,
        "window_start": manifest.window_start.isoformat(),
        "window_end": manifest.window_end.isoformat(),
        "raw_count": manifest.raw_count,
        "normalized_count": manifest.normalized_count,
        "filter_stats": manifest.filter_stats,
        "cache_date": manifest.cache_date,
        "min_reviews_required": config.product.ingestion.min_reviews,
    }
    print(json.dumps(summary, indent=2))

    log_event(
        logger,
        "pulse ingest completed",
        product=args.product,
        stage="cli",
        context={
            "raw_count": manifest.raw_count,
            "normalized_count": manifest.normalized_count,
            "from_cache": manifest.from_cache,
        },
    )

    if manifest.normalized_count < config.product.ingestion.min_reviews:
        return 1
    return 0


def cmd_analyze(args: argparse.Namespace) -> int:
    setup_logging()
    logger = get_logger("pulse.cli")
    config = load_pulse_config(args.product)
    iso_week = resolve_iso_week(args.iso_week, config.product.scheduling)
    cache_date = date.fromisoformat(args.cache_date) if args.cache_date else None

    try:
        report, analysis, run_dir = run_analysis_from_cache(
            args.product,
            iso_week=iso_week,
            cache_date=cache_date,
            skip_llm=args.skip_llm,
            config=config,
            run_id=args.run_id,
        )
    except AnalysisError as exc:
        print(
            json.dumps(
                {
                    "command": "analyze",
                    "product": args.product,
                    "status": "error",
                    "message": str(exc),
                },
                indent=2,
            )
        )
        return 1
    except Exception as exc:
        print(
            json.dumps(
                {
                    "command": "analyze",
                    "product": args.product,
                    "status": "error",
                    "message": str(exc),
                },
                indent=2,
            )
        )
        log_event(
            logger,
            "pulse analyze failed",
            product=args.product,
            stage="cli",
            context={"error": str(exc)},
        )
        return 1

    clustering = analysis.clustering
    groq = analysis.groq_usage
    render_info = None
    if report.themes and run_dir is not None:
        rendered = render_report(report)
        preview_paths = write_preview_artifacts(rendered, run_dir)
        render_info = {
            "anchor": rendered.doc_section.anchor,
            "heading_text": rendered.doc_section.heading_text,
            "content_chars": len(rendered.doc_section.content),
            "email_subject": rendered.email_teaser.subject,
            "idempotency_key": rendered.email_teaser.idempotency_key,
            "preview_files": {key: str(path) for key, path in preview_paths.items()},
        }

    summary = {
        "command": "analyze",
        "product": report.product,
        "iso_week": report.iso_week,
        "status": "success",
        "review_count": report.review_count,
        "theme_count": len(report.themes),
        "cluster_count": len(clustering.ranked_clusters),
        "noise_fraction": round(clustering.noise_fraction, 4),
        "fallback_used": clustering.fallback_used,
        "skip_llm": args.skip_llm,
        "themes": [
            {
                "theme_name": t.theme_name,
                "cluster_size": t.cluster_size,
                "average_rating": t.average_rating,
                "quote_count": len(t.quotes),
            }
            for t in report.themes
        ],
    }
    if render_info:
        summary["render"] = render_info
    if groq:
        summary["groq"] = {
            "requests": groq.requests,
            "tokens_in": groq.tokens_in,
            "tokens_out": groq.tokens_out,
            "total_tokens": groq.total_tokens,
            "re_prompts": groq.re_prompts,
        }
    print(json.dumps(summary, indent=2))
    log_event(
        logger,
        "pulse analyze completed",
        product=args.product,
        iso_week=iso_week,
        stage="cli",
        context={
            "theme_count": len(report.themes),
            "cluster_count": len(clustering.ranked_clusters),
        },
    )
    return 0


def cmd_deliver_doc(args: argparse.Namespace) -> int:
    setup_logging()
    logger = get_logger("pulse.cli")
    config = load_pulse_config(args.product)
    run_dir = Path(args.run_dir)
    doc_id = args.doc_id or config.product.delivery.google_doc_id

    if not doc_id or doc_id.startswith("<"):
        print(
            json.dumps(
                {
                    "command": "deliver-doc",
                    "status": "error",
                    "message": "Set --doc-id or delivery.google_doc_id in product config",
                },
                indent=2,
            )
        )
        return 2

    try:
        doc_section = load_or_render_doc_section(run_dir)
        client = GoogleMcpClient(
            config.settings.mcp_server_url,
            approval_key=config.settings.mcp_approval_key,
        )
        if not args.dry_run:
            health = client.health_check()
            if health.get("status") != "ok":
                raise McpClientError(f"MCP health check failed: {health}")

        result = deliver_doc_section(
            doc_section,
            doc_id,
            client=client,
            data_dir=config.settings.pulse_data_dir,
            dry_run=args.dry_run,
        )
    except (McpClientError, FileNotFoundError, ValueError) as exc:
        print(
            json.dumps(
                {
                    "command": "deliver-doc",
                    "product": args.product,
                    "status": "error",
                    "message": str(exc),
                },
                indent=2,
            )
        )
        return 1

    summary = {
        "command": "deliver-doc",
        "product": args.product,
        "status": "success",
        "anchor": result.anchor,
        "document_id": result.document_id,
        "url": result.url,
        "appended": result.appended,
        "skipped_duplicate": result.skipped_duplicate,
        "dry_run": args.dry_run,
        "mcp_server_url": config.settings.mcp_server_url,
    }
    print(json.dumps(summary, indent=2))
    log_event(
        logger,
        "pulse deliver-doc completed",
        product=args.product,
        stage="cli",
        context={
            "anchor": result.anchor,
            "appended": result.appended,
            "skipped_duplicate": result.skipped_duplicate,
        },
    )
    return 0


def cmd_deliver_email(args: argparse.Namespace) -> int:
    setup_logging()
    logger = get_logger("pulse.cli")
    config = load_pulse_config(args.product)
    run_dir = Path(args.run_dir)
    recipients = args.recipients or config.product.delivery.email.recipients
    email_mode = args.email_mode or config.settings.pulse_email_mode or config.product.delivery.email.default_mode

    if not recipients:
        print(
            json.dumps(
                {
                    "command": "deliver-email",
                    "status": "error",
                    "message": "Set --to or delivery.email.recipients in product config",
                },
                indent=2,
            )
        )
        return 2

    try:
        report = load_report_from_run(run_dir)
        anchor = section_anchor(args.product, report.iso_week)
        doc_url = args.doc_url or doc_url_for_anchor(config.settings.pulse_data_dir, anchor)
        teaser = load_or_render_email_teaser(run_dir, doc_url=doc_url)
        client = GoogleMcpClient(
            config.settings.mcp_server_url,
            approval_key=config.settings.mcp_approval_key,
        )
        if not args.dry_run:
            health = client.health_check()
            if health.get("status") != "ok":
                raise McpClientError(f"MCP health check failed: {health}")

        result = deliver_email_teaser(
            teaser,
            recipients,
            client=client,
            data_dir=config.settings.pulse_data_dir,
            mode=email_mode,
            dry_run=args.dry_run,
        )
    except (McpClientError, FileNotFoundError, ValueError) as exc:
        print(
            json.dumps(
                {
                    "command": "deliver-email",
                    "product": args.product,
                    "status": "error",
                    "message": str(exc),
                },
                indent=2,
            )
        )
        return 1

    summary = {
        "command": "deliver-email",
        "product": args.product,
        "status": "success",
        "idempotency_key": result.idempotency_key,
        "subject": result.subject,
        "recipients": result.recipients,
        "draft_created": result.draft_created,
        "skipped_duplicate": result.skipped_duplicate,
        "draft_id": result.draft_id,
        "message_id": result.message_id,
        "doc_url": result.doc_url,
        "mode": result.mode,
        "dry_run": args.dry_run,
        "mcp_server_url": config.settings.mcp_server_url,
    }
    print(json.dumps(summary, indent=2))
    log_event(
        logger,
        "pulse deliver-email completed",
        product=args.product,
        stage="cli",
        context={
            "idempotency_key": result.idempotency_key,
            "draft_created": result.draft_created,
            "skipped_duplicate": result.skipped_duplicate,
        },
    )
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "run":
        return cmd_run(args)
    if args.command == "dry-run":
        return cmd_dry_run(args)
    if args.command == "backfill":
        return cmd_backfill(args)
    if args.command == "check-failures":
        return cmd_check_failures(args)
    if args.command == "status":
        return cmd_status(args)
    if args.command == "ingest":
        return cmd_ingest(args)
    if args.command == "analyze":
        return cmd_analyze(args)
    if args.command == "deliver-doc":
        return cmd_deliver_doc(args)
    if args.command == "deliver-email":
        return cmd_deliver_email(args)

    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
