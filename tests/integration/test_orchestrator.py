"""End-to-end orchestrator integration tests with mocked MCP and pipeline."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from pulse.agent.models import DocDeliveryResult, EmailDeliveryResult
from pulse.agent.mcp_client import McpClientError
from pulse.agent.orchestrator import OrchestratorError, run_pulse
from pulse.config import load_pulse_config
from pulse.ingestion.cache import CacheManifest
from pulse.ingestion.models import PulseReport, Review, Theme
from pulse.ingestion.service import IngestionResult
from pulse.ledger.store import LedgerStore
from pulse.pipeline.models import AnalysisResult, ClusteringResult
from pulse.render.models import DocSection, EmailTeaser


def _sample_report(iso_week: str = "2026-W24") -> PulseReport:
    return PulseReport(
        product="groww",
        display_name="Groww",
        iso_week=iso_week,
        window_weeks=10,
        review_count=50,
        generated_at=datetime.now(timezone.utc),
        themes=[
            Theme(
                theme_name="Support",
                summary="Users want faster support.",
                quotes=["support is slow"],
            )
        ],
    )


def _ingest_result(reviews: list[Review]) -> IngestionResult:
    manifest = CacheManifest(
        status="success",
        product="groww",
        package_id="com.nextbillion.groww",
        cache_date="2026-06-10",
        window_weeks=10,
        window_start=datetime(2026, 3, 1, tzinfo=timezone.utc),
        window_end=datetime(2026, 6, 10, tzinfo=timezone.utc),
        raw_count=len(reviews),
        normalized_count=len(reviews),
        from_cache=True,
    )
    return IngestionResult(
        product="groww",
        raw_reviews=[],
        normalized_reviews=reviews,
        manifest=manifest,
    )


def _analysis_stub(run_dir: Path):
    report = _sample_report()

    def analyze_fn(product: str, *, iso_week: str, config, run_id: str, **kwargs):
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "report.json").write_text("{}", encoding="utf-8")
        analysis = AnalysisResult(
            themes=report.themes,
            clustering=ClusteringResult(
                labels=[],
                ranked_clusters=[],
                noise_count=0,
                noise_fraction=0.0,
                fallback_used=False,
            ),
        )
        return report, analysis, run_dir

    return analyze_fn


@pytest.fixture
def config(tmp_path):
    cfg = load_pulse_config("groww")
    cfg.settings.pulse_data_dir = tmp_path
    return cfg


@pytest.fixture
def reviews() -> list[Review]:
    return [Review(text=f"Groww review number {i} about trading", rating=3) for i in range(30)]


def test_full_run_dry_run(config, reviews, tmp_path, monkeypatch) -> None:
    run_dir = tmp_path / "runs" / "2026-W24-test"
    ledger = LedgerStore(tmp_path / "ledger" / "pulse.db")

    result = run_pulse(
        "groww",
        iso_week="2026-W24",
        dry_run=True,
        config=config,
        ledger=ledger,
        ingest_fn=lambda *a, **k: _ingest_result(reviews),
        analyze_fn=_analysis_stub(run_dir),
    )

    assert result.status == "completed"
    assert result.dry_run is True
    assert (run_dir / "audit.json").is_file()
    assert ledger.find_completed_run("groww", "2026-W24") is not None


def test_skip_completed_run(config, reviews, tmp_path) -> None:
    ledger = LedgerStore(tmp_path / "ledger" / "pulse.db")
    ledger.create_run("prior-run", "groww", "2026-W24")
    ledger.mark_completed("prior-run")

    result = run_pulse(
        "groww",
        iso_week="2026-W24",
        config=config,
        ledger=ledger,
        ingest_fn=lambda *a, **k: _ingest_result(reviews),
        analyze_fn=_analysis_stub(tmp_path / "runs" / "unused"),
    )

    assert result.status == "skipped"
    assert result.skipped is True
    assert result.run_id == "prior-run"


def test_failed_ingestion_no_delivery(config, tmp_path) -> None:
    ledger = LedgerStore(tmp_path / "ledger" / "pulse.db")

    def fail_ingest(*a, **k):
        raise OrchestratorError("scrape failed")

    result = run_pulse(
        "groww",
        iso_week="2026-W24",
        config=config,
        ledger=ledger,
        ingest_fn=fail_ingest,
        analyze_fn=_analysis_stub(tmp_path / "runs" / "unused"),
    )

    assert result.status == "failed"
    record = ledger.find_latest_run("groww", "2026-W24")
    assert record is not None
    assert record.status == "failed"
    assert record.deliveries == []


def test_partial_failure_allows_gmail_retry(config, reviews, tmp_path, monkeypatch) -> None:
    run_dir = tmp_path / "runs" / "2026-W24-partial"
    ledger = LedgerStore(tmp_path / "ledger" / "pulse.db")
    doc_section = DocSection(
        anchor="groww-2026-W24",
        heading_text="Groww — Weekly Review Pulse — 2026-W24",
        content="section body",
    )
    email_teaser = EmailTeaser(
        idempotency_key="groww-2026-W24-email",
        subject="Groww Weekly Review Pulse — 2026-W24",
        text_body="Read the report",
        html_body="<p>Read the report</p>",
        deep_link="https://docs.google.com/document/d/abc/edit",
    )

    doc_calls = {"count": 0}
    email_calls = {"count": 0}

    def fake_deliver_doc(*args, **kwargs):
        doc_calls["count"] += 1
        return DocDeliveryResult(
            anchor="groww-2026-W24",
            document_id="abc",
            url="https://docs.google.com/document/d/abc/edit",
            appended=True,
            skipped_duplicate=False,
        )

    def fake_deliver_email(*args, **kwargs):
        email_calls["count"] += 1
        if email_calls["count"] == 1:
            raise McpClientError("Gmail unavailable")
        return EmailDeliveryResult(
            idempotency_key="groww-2026-W24-email",
            subject=email_teaser.subject,
            recipients=["ops@example.com"],
            draft_created=True,
            skipped_duplicate=False,
            draft_id="draft-123",
            doc_url="https://docs.google.com/document/d/abc/edit",
        )

    monkeypatch.setenv("GOOGLE_DOC_ID", "abc")
    monkeypatch.setenv("PULSE_EMAIL_RECIPIENTS", "ops@example.com")
    monkeypatch.setattr("pulse.agent.orchestrator.deliver_doc_section", fake_deliver_doc)
    monkeypatch.setattr("pulse.agent.orchestrator.deliver_email_teaser", fake_deliver_email)
    monkeypatch.setattr(
        "pulse.agent.orchestrator.render_report",
        lambda report, **kw: MagicMock(doc_section=doc_section, email_teaser=email_teaser),
    )

    first = run_pulse(
        "groww",
        iso_week="2026-W24",
        config=config,
        ledger=ledger,
        mcp_client=MagicMock(),
        ingest_fn=lambda *a, **k: _ingest_result(reviews),
        analyze_fn=_analysis_stub(run_dir),
    )
    assert first.status == "failed"
    assert doc_calls["count"] == 1
    assert email_calls["count"] == 1
    partial = ledger.find_partial_delivery_run("groww", "2026-W24")
    assert partial is not None

    second = run_pulse(
        "groww",
        iso_week="2026-W24",
        config=config,
        ledger=ledger,
        mcp_client=MagicMock(),
        ingest_fn=lambda *a, **k: _ingest_result(reviews),
        analyze_fn=_analysis_stub(run_dir),
    )
    assert second.status == "completed"
    assert doc_calls["count"] == 2
    assert email_calls["count"] == 2
    completed = ledger.find_completed_run("groww", "2026-W24")
    assert completed is not None
    channels = {d.channel for d in completed.deliveries}
    assert channels == {"google_doc", "gmail"}


def test_rerun_after_completed_skips_delivery(config, reviews, tmp_path, monkeypatch) -> None:
    ledger = LedgerStore(tmp_path / "ledger" / "pulse.db")
    ledger.create_run("done-run", "groww", "2026-W24")
    ledger.add_delivery(
        "done-run",
        channel="google_doc",
        external_id="groww-2026-W24",
        url="https://docs.example/edit",
    )
    ledger.add_delivery(
        "done-run",
        channel="gmail",
        external_id="draft-1",
        idempotency_key="groww-2026-W24-email",
    )
    ledger.mark_completed("done-run")

    ingest_called = {"value": False}

    def ingest(*a, **k):
        ingest_called["value"] = True
        return _ingest_result(reviews)

    result = run_pulse(
        "groww",
        iso_week="2026-W24",
        config=config,
        ledger=ledger,
        ingest_fn=ingest,
        analyze_fn=_analysis_stub(tmp_path / "runs" / "unused"),
    )

    assert result.skipped is True
    assert ingest_called["value"] is False
