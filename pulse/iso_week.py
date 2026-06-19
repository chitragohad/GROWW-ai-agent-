"""ISO 8601 week helpers and default-week resolution (Monday IST policy)."""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone
from typing import Literal, Optional
from zoneinfo import ZoneInfo

from pulse.config import SchedulingConfig

_ISO_WEEK_PATTERN = re.compile(r"^(\d{4})-W(\d{2})$")


def validate_iso_week(iso_week: str) -> str:
    if not _ISO_WEEK_PATTERN.match(iso_week):
        raise ValueError(f"Invalid ISO week format: {iso_week}")
    year, week = parse_iso_week(iso_week)
    # Validate week exists for the year (raises ValueError on bad combos e.g. W53)
    date.fromisocalendar(year, week, 1)
    return iso_week


def parse_iso_week(iso_week: str) -> tuple[int, int]:
    match = _ISO_WEEK_PATTERN.match(iso_week)
    if not match:
        raise ValueError(f"Invalid ISO week format: {iso_week}")
    return int(match.group(1)), int(match.group(2))


def iso_week_to_monday(iso_week: str) -> date:
    year, week = parse_iso_week(iso_week)
    return date.fromisocalendar(year, week, 1)


def format_iso_week(day: date) -> str:
    year, week, _ = day.isocalendar()
    return f"{year}-W{week:02d}"


def previous_iso_week(iso_week: str) -> str:
    monday = iso_week_to_monday(iso_week) - timedelta(days=7)
    return format_iso_week(monday)


def next_iso_week(iso_week: str) -> str:
    monday = iso_week_to_monday(iso_week) + timedelta(days=7)
    return format_iso_week(monday)


def iter_iso_weeks(from_week: str, to_week: str) -> list[str]:
    """Return inclusive ISO week range from ``from_week`` through ``to_week``."""
    validate_iso_week(from_week)
    validate_iso_week(to_week)
    if iso_week_to_monday(from_week) > iso_week_to_monday(to_week):
        raise ValueError(f"from_week {from_week} is after to_week {to_week}")

    weeks: list[str] = []
    current = from_week
    while True:
        weeks.append(current)
        if current == to_week:
            break
        current = next_iso_week(current)
    return weeks


def current_iso_week_utc() -> str:
    today = datetime.now(timezone.utc).date()
    return format_iso_week(today)


def resolve_default_iso_week(
    scheduling: SchedulingConfig,
    *,
    now: Optional[datetime] = None,
) -> str:
    """
    Resolve the default ISO week for ``pulse run`` / ``pulse dry-run``.

    Policy ``previous_complete_before_monday_9am`` (default): on Monday before
    09:00 IST, use the previous ISO week so the scheduled job reports on a
    complete week. Otherwise use the current ISO week in the configured timezone.
    """
    tz = ZoneInfo(scheduling.timezone)
    now_local = (now or datetime.now(timezone.utc)).astimezone(tz)
    current = format_iso_week(now_local.date())

    if scheduling.iso_week_policy == "previous_complete_before_monday_9am":
        weekday = now_local.isoweekday()  # Monday = 1
        if weekday == 1 and now_local.hour < scheduling.monday_cutoff_hour:
            return previous_iso_week(current)

    return current


def resolve_iso_week(
    iso_week: Optional[str],
    scheduling: SchedulingConfig,
    *,
    now: Optional[datetime] = None,
) -> str:
    if iso_week:
        return validate_iso_week(iso_week)
    return resolve_default_iso_week(scheduling, now=now)
