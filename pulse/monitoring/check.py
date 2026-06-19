"""Check ledger for recent failed or partial pulse runs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import List

from pulse.ledger.store import LedgerStore
from pulse.monitoring.alerts import RunAlert, classify_run_record


@dataclass
class FailureCheckResult:
    product: str
    since: datetime
    alerts: List[RunAlert]

    @property
    def failed_count(self) -> int:
        return sum(1 for alert in self.alerts if alert.severity == "failed")

    @property
    def partial_count(self) -> int:
        return sum(1 for alert in self.alerts if alert.severity == "partial")


def check_recent_failures(
    product: str,
    *,
    ledger: LedgerStore,
    since_days: int = 7,
) -> FailureCheckResult:
    since = datetime.now(timezone.utc) - timedelta(days=since_days)
    records = ledger.find_failed_runs_since(product, since=since)
    alerts = [alert for record in records if (alert := classify_run_record(record))]
    return FailureCheckResult(product=product, since=since, alerts=alerts)
