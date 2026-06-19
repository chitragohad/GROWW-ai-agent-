"""PulseReport assembly and run artifact persistence."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from pulse.config import PulseConfig
from pulse.ingestion.models import PulseReport, Theme
from pulse.pipeline.models import AnalysisResult, GroqUsageStats


def build_pulse_report(
    *,
    config: PulseConfig,
    iso_week: str,
    review_count: int,
    themes: List[Theme],
) -> PulseReport:
    return PulseReport(
        product=config.product.product,
        display_name=config.product.display_name,
        iso_week=iso_week,
        window_weeks=config.product.ingestion.window_weeks,
        review_count=review_count,
        generated_at=datetime.now(timezone.utc),
        themes=themes,
    )


def write_report_artifact(
    report: PulseReport,
    analysis: AnalysisResult,
    run_id: str,
    *,
    data_dir: Path,
) -> Path:
    run_dir = data_dir / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / "report.json"

    payload = {
        "report": report.model_dump(mode="json"),
        "clustering": {
            "noise_count": analysis.clustering.noise_count,
            "noise_fraction": analysis.clustering.noise_fraction,
            "fallback_used": analysis.clustering.fallback_used,
            "ranked_clusters": [
                {
                    "label": c.label,
                    "size": c.size,
                    "avg_rating": c.avg_rating,
                    "score": c.score,
                    "sample_count": len(c.samples),
                }
                for c in analysis.clustering.ranked_clusters
            ],
        },
        "scrub_stats": analysis.scrub_stats,
        "groq": _groq_payload(analysis.groq_usage),
    }
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
    return run_dir


def _groq_payload(stats: GroqUsageStats | None) -> dict:
    if stats is None:
        return {}
    return {
        "requests": stats.requests,
        "tokens_in": stats.tokens_in,
        "tokens_out": stats.tokens_out,
        "total_tokens": stats.total_tokens,
        "re_prompts": stats.re_prompts,
        "rpm_headroom": max(0, 30 - stats.requests),
        "tpm_headroom": max(0, 12000 - stats.total_tokens),
        "tpd_headroom": max(0, 100000 - stats.total_tokens),
    }
