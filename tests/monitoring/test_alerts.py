"""Monitoring and production gate tests."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from pulse.agent.orchestrator import OrchestratorError, resolve_email_mode
from pulse.config import AppSettings, load_pulse_config
from pulse.ledger.models import DeliveryRecord, RunRecord
from pulse.ledger.store import LedgerStore
from pulse.monitoring.alerts import RunAlert, classify_run_record, emit_run_alert
from pulse.monitoring.check import check_recent_failures


def _failed_record(*, partial: bool = False) -> RunRecord:
    deliveries = [
        DeliveryRecord(
            channel="google_doc",
            external_id="groww-2026-W24",
            url="https://docs.example/edit",
        )
    ]
    if not partial:
        deliveries = []
    return RunRecord(
        run_id="run-1",
        product="groww",
        iso_week="2026-W24",
        status="failed",
        started_at=datetime.now(timezone.utc),
        error_message="Gmail unavailable" if partial else "Ingestion failed",
        deliveries=deliveries,
    )


def test_classify_failed_run() -> None:
    alert = classify_run_record(_failed_record(partial=False))
    assert alert is not None
    assert alert.severity == "failed"


def test_classify_partial_run() -> None:
    alert = classify_run_record(_failed_record(partial=True))
    assert alert is not None
    assert alert.severity == "partial"


def test_emit_run_alert_logs(caplog) -> None:
    import logging

    caplog.set_level(logging.ERROR, logger="pulse.monitoring.alerts")
    alert = RunAlert(
        severity="failed",
        product="groww",
        iso_week="2026-W24",
        run_id="run-1",
        message="test failure",
    )
    emit_run_alert(alert)
    assert any("pulse alert" in record.message for record in caplog.records)


def test_emit_run_alert_webhook() -> None:
    alert = RunAlert(
        severity="partial",
        product="groww",
        iso_week="2026-W24",
        run_id="run-1",
        message="partial delivery",
    )
    with patch("pulse.monitoring.alerts.urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value.__enter__.return_value.status = 200
        emit_run_alert(alert, webhook_url="https://hooks.example.com/alert")
        mock_urlopen.assert_called_once()


def test_production_send_requires_confirmation() -> None:
    load_pulse_config.cache_clear()
    config = load_pulse_config("groww")
    config.settings = AppSettings(
        pulse_env="production",
        pulse_production_confirmed=False,
    )
    with pytest.raises(OrchestratorError, match="Production email send blocked"):
        resolve_email_mode(config)


def test_production_send_allowed_with_confirmation() -> None:
    config = load_pulse_config("groww")
    config.settings = AppSettings(
        pulse_env="production",
        pulse_production_confirmed=False,
    )
    mode = resolve_email_mode(config, production_confirmed=True)
    assert mode == "send"


def test_development_defaults_to_draft() -> None:
    config = load_pulse_config("groww")
    config.settings = AppSettings(pulse_env="development")
    assert resolve_email_mode(config) == "draft"


def test_check_recent_failures(tmp_path) -> None:
    ledger = LedgerStore(tmp_path / "pulse.db")
    ledger.create_run("run-1", "groww", "2026-W24")
    ledger.mark_failed("run-1", "boom")

    result = check_recent_failures("groww", ledger=ledger, since_days=7)
    assert result.failed_count == 1
    assert result.alerts[0].severity == "failed"
