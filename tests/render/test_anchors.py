"""Anchor and heading convention tests."""

from __future__ import annotations

import pytest

from pulse.render.anchors import (
    email_idempotency_key,
    email_subject,
    section_anchor,
    section_heading_text,
    validate_iso_week,
)


def test_section_anchor_deterministic() -> None:
    assert section_anchor("groww", "2026-W23") == "groww-2026-W23"


def test_section_heading_text() -> None:
    assert section_heading_text("Groww", "2026-W23") == "Groww — Weekly Review Pulse — 2026-W23"


def test_email_idempotency_key() -> None:
    assert email_idempotency_key("groww", "2026-W23") == "groww-2026-W23-email"


def test_email_subject() -> None:
    assert email_subject("Groww", "2026-W23") == "Groww Weekly Review Pulse — 2026-W23"


@pytest.mark.parametrize("iso_week", ["2026-W00", "2026-W54", "bad-week"])
def test_invalid_iso_week_rejected(iso_week: str) -> None:
    with pytest.raises(ValueError):
        validate_iso_week(iso_week)
