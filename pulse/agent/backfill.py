"""Backfill orchestration for sequential ISO week runs."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Literal, Optional

from pulse.agent.orchestrator import RunResult, run_pulse
from pulse.config import PulseConfig, load_pulse_config
from pulse.iso_week import iter_iso_weeks
from pulse.logging import get_logger, log_event

logger = get_logger("pulse.agent.backfill")


@dataclass
class BackfillResult:
    product: str
    from_week: str
    to_week: str
    weeks: List[str]
    results: List[RunResult] = field(default_factory=list)

    @property
    def completed_count(self) -> int:
        return sum(1 for r in self.results if r.status == "completed")

    @property
    def skipped_count(self) -> int:
        return sum(1 for r in self.results if r.status == "skipped")

    @property
    def failed_count(self) -> int:
        return sum(1 for r in self.results if r.status == "failed")


def run_backfill(
    product: str,
    *,
    from_week: str,
    to_week: str,
    dry_run: bool = False,
    force_refresh: bool = False,
    email_mode: Optional[Literal["draft", "send"]] = None,
    production_confirmed: bool = False,
    config: Optional[PulseConfig] = None,
) -> BackfillResult:
    """Run pulse sequentially for each ISO week, respecting ledger idempotency."""
    config = config or load_pulse_config(product)
    weeks = iter_iso_weeks(from_week, to_week)
    backfill = BackfillResult(product=product, from_week=from_week, to_week=to_week, weeks=weeks)

    log_event(
        logger,
        "backfill started",
        product=product,
        stage="backfill",
        context={"from_week": from_week, "to_week": to_week, "week_count": len(weeks), "dry_run": dry_run},
    )

    for index, iso_week in enumerate(weeks):
        refresh = force_refresh and index == 0
        result = run_pulse(
            product,
            iso_week=iso_week,
            dry_run=dry_run,
            force_refresh=refresh,
            email_mode=email_mode,
            production_confirmed=production_confirmed,
            config=config,
        )
        backfill.results.append(result)
        log_event(
            logger,
            "backfill week finished",
            run_id=result.run_id,
            product=product,
            iso_week=iso_week,
            stage="backfill",
            context={"status": result.status, "week_index": index + 1, "week_count": len(weeks)},
        )

    log_event(
        logger,
        "backfill completed",
        product=product,
        stage="backfill",
        context={
            "completed": backfill.completed_count,
            "skipped": backfill.skipped_count,
            "failed": backfill.failed_count,
        },
    )
    return backfill
