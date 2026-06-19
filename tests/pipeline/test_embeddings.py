"""Embedding cache behavior."""

from __future__ import annotations

from pathlib import Path

import pytest

from pulse.config import EmbeddingConfig
from pulse.ingestion.models import Review
from pulse.pipeline.embeddings import EmbeddingStore, embed_reviews


@pytest.fixture
def embedding_config() -> EmbeddingConfig:
    return EmbeddingConfig(
        provider="sentence-transformers",
        model="BAAI/bge-small-en-v1.5",
        batch_size=64,
    )


def test_embedding_cache_prevents_recompute(
    embedding_config: EmbeddingConfig,
    tmp_path: Path,
) -> None:
    store = EmbeddingStore(cache_dir=tmp_path)
    reviews = [Review(text=f"Review number {i} about trading issues", rating=2) for i in range(25)]
    calls = {"count": 0}

    def fake_embed(texts: list[str]) -> list[list[float]]:
        calls["count"] += 1
        return [[float(len(t)), 0.1, 0.2] for t in texts]

    embed_reviews(reviews, embedding_config, store=store, embed_batch=fake_embed)
    embed_reviews(reviews, embedding_config, store=store, embed_batch=fake_embed)
    assert calls["count"] == 1


def test_embed_reviews_requires_minimum(embedding_config: EmbeddingConfig) -> None:
    reviews = [Review(text="short review text here", rating=1) for _ in range(10)]
    with pytest.raises(Exception):
        embed_reviews(reviews, embedding_config, embed_batch=lambda t: [[0.0]] * len(t))
