"""ISO week helper tests."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from pulse.config import SchedulingConfig
from pulse.iso_week import (
    iter_iso_weeks,
    next_iso_week,
    previous_iso_week,
    resolve_default_iso_week,
    validate_iso_week,
)


def test_validate_iso_week() -> None:
    assert validate_iso_week("2026-W24") == "2026-W24"
    with pytest.raises(ValueError):
        validate_iso_week("2026-W99")


def test_iter_iso_weeks_inclusive() -> None:
    weeks = iter_iso_weeks("2026-W20", "2026-W22")
    assert weeks == ["2026-W20", "2026-W21", "2026-W22"]


def test_iter_iso_weeks_year_boundary() -> None:
    weeks = iter_iso_weeks("2025-W52", "2026-W02")
    assert weeks[0] == "2025-W52"
    assert weeks[-1] == "2026-W02"
    assert len(weeks) == 3


def test_iter_iso_weeks_rejects_inverted_range() -> None:
    with pytest.raises(ValueError):
        iter_iso_weeks("2026-W22", "2026-W20")


def test_previous_and_next_iso_week() -> None:
    assert previous_iso_week("2026-W02") == "2026-W01"
    assert next_iso_week("2026-W01") == "2026-W02"


def test_monday_morning_ist_uses_previous_week() -> None:
    scheduling = SchedulingConfig(
        timezone="Asia/Kolkata",
        iso_week_policy="previous_complete_before_monday_9am",
        monday_cutoff_hour=9,
    )
    # Monday 2026-06-08 08:30 IST -> still week 23
    monday_morning = datetime(2026, 6, 8, 3, 0, tzinfo=timezone.utc)  # 08:30 IST
    assert resolve_default_iso_week(scheduling, now=monday_morning) == "2026-W23"


def test_monday_after_cutoff_uses_current_week() -> None:
    scheduling = SchedulingConfig(
        timezone="Asia/Kolkata",
        iso_week_policy="previous_complete_before_monday_9am",
        monday_cutoff_hour=9,
    )
    monday_late = datetime(2026, 6, 8, 4, 0, tzinfo=timezone.utc)  # 09:30 IST
    assert resolve_default_iso_week(scheduling, now=monday_late) == "2026-W24"


def test_current_policy_always_uses_local_week() -> None:
    scheduling = SchedulingConfig(
        timezone="Asia/Kolkata",
        iso_week_policy="current",
    )
    monday_morning = datetime(2026, 6, 8, 3, 0, tzinfo=timezone.utc)
    assert resolve_default_iso_week(scheduling, now=monday_morning) == "2026-W24"
