"""Local BGE embedding with disk cache."""

from __future__ import annotations

import hashlib
import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Callable, List, Optional

import numpy as np

from pulse.config import EmbeddingConfig, project_root
from pulse.ingestion.models import Review

DEFAULT_BGE_MODEL = "BAAI/bge-small-en-v1.5"


class EmbeddingError(Exception):
    pass


def embedding_cache_key(scrubbed_text: str, rating: int, model: str) -> str:
    payload = f"{model}|{scrubbed_text}|{rating}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def default_cache_dir() -> Path:
    data_dir = os.environ.get("PULSE_DATA_DIR")
    base = Path(data_dir) if data_dir else project_root() / "data"
    return base / "embeddings"


class EmbeddingStore:
    def __init__(self, cache_dir: Optional[Path] = None) -> None:
        self.cache_dir = cache_dir or default_cache_dir()
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        return self.cache_dir / f"{key}.json"

    def get(self, key: str) -> Optional[List[float]]:
        path = self._path(key)
        if not path.is_file():
            return None
        with path.open(encoding="utf-8") as handle:
            data = json.load(handle)
        return data["embedding"]

    def set(self, key: str, embedding: List[float]) -> None:
        with self._path(key).open("w", encoding="utf-8") as handle:
            json.dump({"embedding": embedding}, handle)


def embed_reviews(
    reviews: List[Review],
    config: EmbeddingConfig,
    *,
    store: Optional[EmbeddingStore] = None,
    embed_batch: Optional[Callable[[List[str]], List[List[float]]]] = None,
) -> np.ndarray:
    """
    Embed scrubbed review text. Rating is used in cache key only, not in model input.
    Returns array shape (n_reviews, dim).
    """
    if len(reviews) < 20:
        raise EmbeddingError(f"Need at least 20 reviews to embed, got {len(reviews)}")

    store = store or EmbeddingStore()
    keys = [embedding_cache_key(r.text, r.rating, config.model) for r in reviews]
    vectors: List[Optional[List[float]]] = [store.get(k) for k in keys]

    missing_indices = [i for i, vec in enumerate(vectors) if vec is None]
    if missing_indices:
        if embed_batch is None:
            embed_batch = _embed_batch_factory(config)
        for start in range(0, len(missing_indices), config.batch_size):
            batch_indices = missing_indices[start : start + config.batch_size]
            batch_texts = [reviews[i].text for i in batch_indices]
            batch_vectors = embed_batch(batch_texts)
            for idx, vector in zip(batch_indices, batch_vectors):
                vectors[idx] = vector
                store.set(keys[idx], vector)

    return np.array(vectors, dtype=np.float32)


def _embed_batch_factory(config: EmbeddingConfig) -> Callable[[List[str]], List[List[float]]]:
    provider = config.provider.lower().replace("_", "-")
    if provider in {"sentence-transformers", "bge", "huggingface"}:
        return _bge_embed_batch_factory(config)
    raise EmbeddingError(f"Unsupported embedding provider: {config.provider}")


@lru_cache(maxsize=2)
def _load_sentence_transformer(model_name: str):
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise EmbeddingError(
            "sentence-transformers is required for BGE embeddings; "
            "install with: pip install sentence-transformers"
        ) from exc
    return SentenceTransformer(model_name)


def _bge_embed_batch_factory(config: EmbeddingConfig) -> Callable[[List[str]], List[List[float]]]:
    model_name = config.model or DEFAULT_BGE_MODEL

    def _embed(texts: List[str]) -> List[List[float]]:
        model = _load_sentence_transformer(model_name)
        encoded = model.encode(
            texts,
            batch_size=min(config.batch_size, len(texts)),
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return encoded.tolist()

    return _embed
