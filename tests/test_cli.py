"""CLI run and status tests."""

from __future__ import annotations

import json

from pulse.agent.orchestrator import RunResult
from pulse.cli import main


def test_pulse_run_dry_run(monkeypatch, capsys) -> None:
    mock_result = RunResult(
        run_id="2026-W24-test",
        product="groww",
        iso_week="2026-W24",
        status="completed",
        dry_run=True,
        stage_durations={"ingestion": 1.2, "analysis": 40.5},
    )
    monkeypatch.setattr("pulse.cli.run_pulse", lambda *a, **k: mock_result)

    exit_code = main(["run", "--product", "groww", "--iso-week", "2026-W24", "--dry-run"])
    assert exit_code == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["product"] == "groww"
    assert payload["status"] == "completed"
    assert payload["dry_run"] is True
    assert payload["stage_durations_seconds"]["analysis"] == 40.5


def test_pulse_dry_run_command(monkeypatch, capsys) -> None:
    mock_result = RunResult(
        run_id="2026-W24-test",
        product="groww",
        iso_week="2026-W24",
        status="completed",
        dry_run=True,
    )
    captured: dict = {}

    def fake_run_pulse(*args, **kwargs):
        captured.update(kwargs)
        return mock_result

    monkeypatch.setattr("pulse.cli.run_pulse", fake_run_pulse)

    exit_code = main(["dry-run", "--product", "groww", "--iso-week", "2026-W24"])
    assert exit_code == 0
    assert captured["dry_run"] is True

    payload = json.loads(capsys.readouterr().out)
    assert payload["command"] == "dry-run"


def test_pulse_status_not_found(tmp_path, monkeypatch, capsys) -> None:
    from pulse.config import load_pulse_config

    load_pulse_config.cache_clear()
    monkeypatch.setenv("PULSE_DATA_DIR", str(tmp_path))

    exit_code = main(["status", "--product", "groww", "--iso-week", "2026-W99"])
    assert exit_code == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "not_found"


def test_pulse_status_shows_deliveries(tmp_path, monkeypatch, capsys) -> None:
    from pulse.config import load_pulse_config

    load_pulse_config.cache_clear()
    monkeypatch.setenv("PULSE_DATA_DIR", str(tmp_path))
    from pulse.ledger.store import LedgerStore

    ledger = LedgerStore(tmp_path / "ledger" / "pulse.db")
    ledger.create_run("run-1", "groww", "2026-W24")
    ledger.add_delivery(
        "run-1",
        channel="google_doc",
        external_id="groww-2026-W24",
        url="https://docs.example/edit",
    )
    ledger.add_delivery(
        "run-1",
        channel="gmail",
        external_id="draft-99",
        idempotency_key="groww-2026-W24-email",
    )
    ledger.mark_completed("run-1")

    exit_code = main(["status", "--product", "groww", "--iso-week", "2026-W24"])
    assert exit_code == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "completed"
    assert len(payload["deliveries"]) == 2
    channels = {d["channel"] for d in payload["deliveries"]}
    assert channels == {"google_doc", "gmail"}
