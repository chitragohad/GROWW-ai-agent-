"""Backfill CLI and orchestration tests."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from pulse.agent.backfill import run_backfill
from pulse.agent.orchestrator import RunResult
from pulse.cli import main
from pulse.config import load_pulse_config
from pulse.ledger.store import LedgerStore


def _mock_run_result(iso_week: str, status: str = "completed", skipped: bool = False) -> RunResult:
    return RunResult(
        run_id=f"{iso_week}-test",
        product="groww",
        iso_week=iso_week,
        status=status,  # type: ignore[arg-type]
        skipped=skipped,
    )


def test_backfill_skips_completed_weeks(tmp_path, monkeypatch) -> None:
    load_pulse_config.cache_clear()
    monkeypatch.setenv("PULSE_DATA_DIR", str(tmp_path))

    ledger = LedgerStore(tmp_path / "ledger" / "pulse.db")
    ledger.create_run("done", "groww", "2026-W21")
    ledger.mark_completed("done")

    calls: list[str] = []

    def fake_run_pulse(product, *, iso_week, **kwargs):
        calls.append(iso_week)
        if iso_week == "2026-W21":
            return _mock_run_result(iso_week, status="skipped", skipped=True)
        return _mock_run_result(iso_week)

    monkeypatch.setattr("pulse.agent.backfill.run_pulse", fake_run_pulse)

    config = load_pulse_config("groww")
    backfill = run_backfill(
        "groww",
        from_week="2026-W20",
        to_week="2026-W22",
        dry_run=True,
        config=config,
    )

    assert calls == ["2026-W20", "2026-W21", "2026-W22"]
    assert backfill.skipped_count == 1
    assert backfill.completed_count == 2


def test_backfill_cli(monkeypatch, capsys) -> None:
    mock_backfill = MagicMock()
    mock_backfill.product = "groww"
    mock_backfill.from_week = "2026-W20"
    mock_backfill.to_week = "2026-W22"
    mock_backfill.weeks = ["2026-W20", "2026-W21", "2026-W22"]
    mock_backfill.results = [
        _mock_run_result("2026-W20"),
        _mock_run_result("2026-W21", status="skipped", skipped=True),
        _mock_run_result("2026-W22"),
    ]
    mock_backfill.completed_count = 2
    mock_backfill.skipped_count = 1
    mock_backfill.failed_count = 0

    monkeypatch.setattr("pulse.cli.run_backfill", lambda *a, **k: mock_backfill)

    exit_code = main(
        [
            "backfill",
            "--product",
            "groww",
            "--from",
            "2026-W20",
            "--to",
            "2026-W22",
            "--dry-run",
        ]
    )
    assert exit_code == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["command"] == "backfill"
    assert payload["skipped"] == 1
    assert payload["completed"] == 2
    assert len(payload["weeks"]) == 3
