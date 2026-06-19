"""Pipeline service orchestration."""

from __future__ import annotations

import numpy as np
import pytest

from pulse.config import load_pulse_config
from pulse.ingestion.models import Review
from pulse.pipeline.service import AnalysisError, run_analysis


def _reviews(n: int = 30) -> list[Review]:
    return [
        Review(text=f"Review about trading bug number {i} on Groww app", rating=1 + (i % 5))
        for i in range(n)
    ]


def test_run_analysis_aborts_below_ml_floor() -> None:
    config = load_pulse_config("groww")
    with pytest.raises(AnalysisError):
        run_analysis(_reviews(10), config, iso_week="2026-W23", write_report=False)


def test_run_analysis_skip_llm(tmp_path) -> None:
    config = load_pulse_config("groww")
    config.settings.pulse_data_dir = tmp_path
    reviews = _reviews(30)

    def fake_embed(texts: list[str]) -> list[list[float]]:
        return [list(np.random.default_rng(hash(t) % 2**32).normal(0, 1, 8)) for t in texts]

    report, analysis, run_dir = run_analysis(
        reviews,
        config,
        iso_week="2026-W23",
        skip_llm=True,
        embed_batch=fake_embed,
    )

    assert report.review_count == 30
    assert analysis.groq_usage is None
    assert len(analysis.clustering.ranked_clusters) >= 1
    assert run_dir is not None
