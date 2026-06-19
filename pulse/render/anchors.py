"""Deterministic anchor and heading conventions for idempotent delivery."""

from __future__ import annotations

import re

_ISO_WEEK_PATTERN = re.compile(r"^\d{4}-W(0[1-9]|[1-4]\d|5[0-3])$")


def validate_iso_week(iso_week: str) -> str:
    if not _ISO_WEEK_PATTERN.match(iso_week):
        raise ValueError(f"Invalid ISO week format: {iso_week}")
    return iso_week


def section_anchor(product: str, iso_week: str) -> str:
    validate_iso_week(iso_week)
    return f"{product}-{iso_week}"


def section_heading_text(display_name: str, iso_week: str) -> str:
    validate_iso_week(iso_week)
    return f"{display_name} — Weekly Review Pulse — {iso_week}"


def email_idempotency_key(product: str, iso_week: str) -> str:
    return f"{section_anchor(product, iso_week)}-email"


def email_subject(display_name: str, iso_week: str) -> str:
    validate_iso_week(iso_week)
    return f"{display_name} Weekly Review Pulse — {iso_week}"
