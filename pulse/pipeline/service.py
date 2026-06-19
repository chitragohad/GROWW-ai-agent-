"""Orchestrate Phase 2a clustering and Phase 2b summarization."""

from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Callable, List, Optional

from pulse.config import PulseConfig, load_pulse_config
from pulse.ingestion.cache import load_cached_reviews
from pulse.ingestion.models import PulseReport, Review
from pulse.models.report import build_pulse_report, write_report_artifact
from pulse.pipeline.clustering import cluster_reviews
from pulse.pipeline.embeddings import EmbeddingStore, embed_reviews
from pulse.pipeline.models import AnalysisResult, GroqUsageStats
from pulse.pipeline.scrubber import scrub_reviews
from pulse.pipeline.summarizer import GroqClient, summarize_clusters

logger = logging.getLogger(__name__)

ML_FLOOR = 20


class AnalysisError(Exception):
    pass


def find_latest_cache_date(product: str, *, data_dir: Path) -> Optional[date]:
    cache_root = data_dir / "cache" / product
    if not cache_root.is_dir():
        return None
    dates: List[date] = []
    for child in cache_root.iterdir():
        if child.is_dir():
            try:
                dates.append(date.fromisoformat(child.name))
            except ValueError:
                continue
    return max(dates) if dates else None


def run_analysis(
    reviews: List[Review],
    config: PulseConfig,
    *,
    iso_week: str,
    skip_llm: bool = False,
    embed_batch: Optional[Callable[[List[str]], List[List[float]]]] = None,
    groq_client: Optional[GroqClient] = None,
    embedding_store: Optional[EmbeddingStore] = None,
    run_id: Optional[str] = None,
    write_report: bool = True,
) -> tuple[PulseReport, AnalysisResult, Optional[Path]]:
    """Run scrub → embed → cluster → (optional) summarize → PulseReport."""
    if len(reviews) < ML_FLOOR:
        raise AnalysisError(f"Need at least {ML_FLOOR} reviews, got {len(reviews)}")

    pipeline = config.pipeline
    scrubbed, scrub_stats = scrub_reviews(reviews) if pipeline.safety.scrub_pii else (reviews, {})

    embeddings = embed_reviews(
        scrubbed,
        pipeline.embedding,
        store=embedding_store,
        embed_batch=embed_batch,
    )

    clustering = cluster_reviews(scrubbed, embeddings, pipeline)
    _truncate_cluster_samples(clustering.ranked_clusters, pipeline.safety.max_review_chars)

    groq_usage: Optional[GroqUsageStats] = None
    themes = []
    if not skip_llm and clustering.ranked_clusters:
        themes, groq_usage = summarize_clusters(
            clustering.ranked_clusters,
            pipeline.summarization,
            groq_client=groq_client,
        )
        _log_groq_usage(groq_usage, pipeline.summarization.max_tokens_per_run)

    report = build_pulse_report(
        config=config,
        iso_week=iso_week,
        review_count=len(reviews),
        themes=themes,
    )

    analysis = AnalysisResult(
        themes=themes,
        clustering=clustering,
        groq_usage=groq_usage,
        scrub_stats=scrub_stats or None,
    )

    run_dir: Optional[Path] = None
    if write_report:
        rid = run_id or _default_run_id(iso_week)
        run_dir = write_report_artifact(report, analysis, rid, data_dir=config.settings.pulse_data_dir)

    return report, analysis, run_dir


def run_analysis_from_cache(
    product: str,
    *,
    iso_week: str,
    cache_date: Optional[date] = None,
    skip_llm: bool = False,
    config: Optional[PulseConfig] = None,
    **kwargs,
) -> tuple[PulseReport, AnalysisResult, Optional[Path]]:
    """Load normalized reviews from cache and run analysis."""
    config = config or load_pulse_config(product)
    data_dir = config.settings.pulse_data_dir
    resolved_date = cache_date or find_latest_cache_date(product, data_dir=data_dir)
    if resolved_date is None:
        raise AnalysisError(f"No cache found for product {product}")

    _, normalized, manifest = load_cached_reviews(
        product,
        data_dir=data_dir,
        cache_date=resolved_date,
    )
    logger.info(
        "Loaded %d normalized reviews from cache %s",
        len(normalized),
        manifest.cache_date,
    )
    return run_analysis(
        normalized,
        config,
        iso_week=iso_week,
        skip_llm=skip_llm,
        **kwargs,
    )


def _truncate_cluster_samples(clusters, max_chars: int) -> None:
    for cluster in clusters:
        cluster.samples = [
            Review(text=s.text[:max_chars], rating=s.rating) for s in cluster.samples
        ]


def _default_run_id(iso_week: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{iso_week}-{stamp}-{uuid.uuid4().hex[:8]}"


def _log_groq_usage(stats: GroqUsageStats, max_tokens_per_run: int) -> None:
    rpm_headroom = max(0, 30 - stats.requests)
    tpm_headroom = max(0, 12000 - stats.total_tokens)
    tpd_headroom = max(0, 100000 - stats.total_tokens)
    logger.info(
        "Groq usage: requests=%d tokens_in=%d tokens_out=%d re_prompts=%d "
        "rpm_headroom=%d tpm_headroom=%d tpd_headroom=%d run_budget_headroom=%d",
        stats.requests,
        stats.tokens_in,
        stats.tokens_out,
        stats.re_prompts,
        rpm_headroom,
        tpm_headroom,
        tpd_headroom,
        max(0, max_tokens_per_run - stats.total_tokens),
    )
