"""Ledger store unit tests."""

from __future__ import annotations

import pytest

from pulse.ledger.store import LedgerStore


@pytest.fixture
def ledger(tmp_path) -> LedgerStore:
    return LedgerStore(tmp_path / "pulse.db")


def test_create_and_complete_run(ledger: LedgerStore) -> None:
    ledger.create_run("run-1", "groww", "2026-W24", window_weeks=10)
    ledger.update_run_metrics("run-1", review_count=100, window_weeks=10)
    ledger.add_delivery(
        "run-1",
        channel="google_doc",
        external_id="groww-2026-W24",
        url="https://docs.google.com/document/d/abc/edit",
        idempotency_key="groww-2026-W24",
    )
    record = ledger.mark_completed("run-1")

    assert record.status == "completed"
    assert record.review_count == 100
    assert len(record.deliveries) == 1
    assert record.deliveries[0].channel == "google_doc"


def test_find_completed_run(ledger: LedgerStore) -> None:
    ledger.create_run("run-1", "groww", "2026-W24")
    ledger.mark_completed("run-1")

    found = ledger.find_completed_run("groww", "2026-W24")
    assert found is not None
    assert found.run_id == "run-1"


def test_unique_completed_constraint(ledger: LedgerStore) -> None:
    ledger.create_run("run-1", "groww", "2026-W24")
    ledger.mark_completed("run-1")

    ledger.create_run("run-2", "groww", "2026-W24")
    with pytest.raises(Exception):
        ledger.mark_completed("run-2")


def test_partial_delivery_run_detection(ledger: LedgerStore) -> None:
    ledger.create_run("run-1", "groww", "2026-W24")
    ledger.add_delivery(
        "run-1",
        channel="google_doc",
        external_id="groww-2026-W24",
        url="https://docs.example/edit",
    )
    ledger.mark_failed("run-1", "Gmail draft failed")

    partial = ledger.find_partial_delivery_run("groww", "2026-W24")
    assert partial is not None
    assert partial.run_id == "run-1"
    assert len(partial.deliveries) == 1


def test_reopen_run(ledger: LedgerStore) -> None:
    ledger.create_run("run-1", "groww", "2026-W24")
    ledger.mark_failed("run-1", "temporary error")
    ledger.reopen_run("run-1")

    latest = ledger.find_latest_run("groww", "2026-W24")
    assert latest is not None
    assert latest.status == "pending"
    assert latest.error_message is None
