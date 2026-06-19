"""Shared fixtures for render tests."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from pulse.ingestion.models import ActionIdea, PulseReport, Theme


@pytest.fixture
def sample_report() -> PulseReport:
    return PulseReport(
        product="groww",
        display_name="Groww",
        iso_week="2026-W23",
        window_weeks=10,
        review_count=884,
        generated_at=datetime(2026, 6, 8, 10, 30, tzinfo=timezone.utc),
        themes=[
            Theme(
                theme_name="Poor Support",
                summary="Users report glitches and unresponsive customer care.",
                quotes=[
                    "The app is riddled with glitches and faults",
                    "coustomer care team is very very rude and irritated",
                ],
                action_ideas=[
                    ActionIdea(
                        title="Improve Customer Support",
                        detail="Reduce response times and train agents on empathy.",
                    )
                ],
                cluster_size=88,
                average_rating=1.3,
            ),
            Theme(
                theme_name="Ease of Use",
                summary="Users praise the simple interface and easy SIP setup.",
                quotes=["easy demate opening process.. easy to buy and sell"],
                action_ideas=[
                    ActionIdea(
                        title="Add News Section",
                        detail="Provide a dedicated news feed for stock analysis.",
                    )
                ],
                cluster_size=74,
                average_rating=4.9,
            ),
        ],
    )


@pytest.fixture
def golden_dir() -> Path:
    return Path(__file__).resolve().parent / "golden"


def load_golden(name: str, golden_dir: Path) -> str:
    return (golden_dir / name).read_text(encoding="utf-8").rstrip("\n")


def load_golden_json(name: str, golden_dir: Path):
    return json.loads((golden_dir / name).read_text(encoding="utf-8"))
