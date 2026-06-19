"""CLI analyze command."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

from pulse.cli import main
from pulse.ingestion.models import PulseReport, Theme
from pulse.pipeline.models import AnalysisResult, ClusteringResult


def test_analyze_cli_success() -> None:
    fake_report = PulseReport(
        product="groww",
        display_name="Groww",
        iso_week="2026-W23",
        window_weeks=10,
        review_count=100,
        generated_at=datetime(2026, 6, 10, tzinfo=timezone.utc),
        themes=[Theme(theme_name="Test", summary="s", quotes=["q"])],
    )
    fake_analysis = AnalysisResult(
        themes=fake_report.themes,
        clustering=ClusteringResult(
            labels=[0, 1],
            ranked_clusters=[],
            noise_count=0,
            noise_fraction=0.0,
        ),
    )

    with patch("pulse.cli.run_analysis_from_cache", return_value=(fake_report, fake_analysis, None)):
        exit_code = main(["analyze", "--product", "groww", "--iso-week", "2026-W23", "--skip-llm"])

    assert exit_code == 0
