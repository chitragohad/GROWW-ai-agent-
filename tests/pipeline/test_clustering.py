"""Clustering ranking, sampling, and fallbacks."""

from __future__ import annotations

import numpy as np
import pytest

from pulse.config import load_pipeline_config
from pulse.ingestion.models import Review
from pulse.pipeline.clustering import cluster_reviews, select_cluster_samples


def _synthetic_reviews(n: int = 60) -> list[Review]:
    templates = [
        ("Withdrawal pending for days without any update from support", 1),
        ("App crashes when opening portfolio during market hours", 2),
        ("Love the clean UI and easy SIP setup experience", 5),
        ("Charts load slowly on older Android phones", 2),
        ("Great mutual fund research tools and recommendations", 5),
    ]
    reviews = []
    for i in range(n):
        text, rating = templates[i % len(templates)]
        reviews.append(Review(text=f"{text} variant {i}", rating=rating))
    return reviews


def _synthetic_embeddings(reviews: list[Review]) -> np.ndarray:
    groups = []
    for i, review in enumerate(reviews):
        base = [0.0, 0.0, 0.0]
        if review.rating <= 2:
            base[0] = 1.0
        elif review.rating >= 4:
            base[1] = 1.0
        else:
            base[2] = 1.0
        noise = np.random.default_rng(i).normal(0, 0.05, 3)
        groups.append(np.array(base) + noise)
    return np.array(groups, dtype=np.float32)


def test_cluster_reviews_returns_ranked_clusters() -> None:
    np.random.seed(42)
    reviews = _synthetic_reviews()
    embeddings = _synthetic_embeddings(reviews)
    pipeline = load_pipeline_config()

    result = cluster_reviews(reviews, embeddings, pipeline)

    assert len(result.ranked_clusters) >= 2
    assert len(result.ranked_clusters) <= pipeline.summarization.max_themes
    assert result.ranked_clusters[0].score >= result.ranked_clusters[-1].score
    for cluster in result.ranked_clusters:
        assert cluster.samples
        assert len(cluster.samples) <= pipeline.summarization.max_samples_per_cluster


def test_select_cluster_samples_respects_max() -> None:
    reviews = _synthetic_reviews(30)
    embeddings = _synthetic_embeddings(reviews)
    indices = list(range(15))
    samples = select_cluster_samples(indices, reviews, embeddings, max_samples=5, random_state=42)
    assert len(samples) == 5


def test_clustering_aborts_below_ml_floor() -> None:
    pipeline = load_pipeline_config()
    reviews = [Review(text="too few reviews for clustering", rating=1) for _ in range(5)]
    embeddings = np.random.rand(5, 3).astype(np.float32)
    with pytest.raises(Exception):
        cluster_reviews(reviews, embeddings, pipeline)


@pytest.mark.integration
def test_groww_cache_clustering(project_root) -> None:
    """Integration: cluster real cached Groww reviews if cache exists."""
    from datetime import date
    from pathlib import Path

    from pulse.config import load_pulse_config
    from pulse.ingestion.cache import load_cached_reviews
    from pulse.pipeline.embeddings import embed_reviews
    from pulse.pipeline.service import find_latest_cache_date

    config = load_pulse_config("groww")
    data_dir = config.settings.pulse_data_dir
    cache_date = find_latest_cache_date("groww", data_dir=data_dir)
    if cache_date is None:
        pytest.skip("No Groww cache available")

    _, normalized, _ = load_cached_reviews("groww", data_dir=data_dir, cache_date=cache_date)
    if len(normalized) < 20:
        pytest.skip("Insufficient cached reviews")

    def fake_embed(texts: list[str]) -> list[list[float]]:
        return [list(np.random.default_rng(hash(t) % 2**32).normal(0, 1, 8)) for t in texts]

    embeddings = embed_reviews(
        normalized,
        config.pipeline.embedding,
        embed_batch=fake_embed,
    )
    result = cluster_reviews(normalized, embeddings, config.pipeline)
    assert len(result.ranked_clusters) >= 1 or result.fallback_used is not None
