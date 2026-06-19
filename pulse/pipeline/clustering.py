"""UMAP + HDBSCAN clustering with ranking and fallbacks."""

from __future__ import annotations

import logging
from typing import List, Optional, Tuple

import hdbscan
import numpy as np
import umap
from sklearn.metrics.pairwise import cosine_distances

from pulse.config import ClusteringConfig, PipelineConfig
from pulse.ingestion.models import Review
from pulse.pipeline.models import ClusteringResult, RankedCluster

logger = logging.getLogger(__name__)

MEGA_CLUSTER_FRACTION = 0.80


class ClusteringError(Exception):
    pass


def cluster_reviews(
    reviews: List[Review],
    embeddings: np.ndarray,
    pipeline_config: PipelineConfig,
    *,
    max_themes: Optional[int] = None,
) -> ClusteringResult:
    """Run UMAP → HDBSCAN with fallbacks; rank and sample top clusters."""
    if len(reviews) != len(embeddings):
        raise ClusteringError("Review count must match embedding count")
    if len(reviews) < 20:
        raise ClusteringError(f"Need at least 20 reviews to cluster, got {len(reviews)}")

    max_themes = max_themes or pipeline_config.summarization.max_themes
    max_samples = pipeline_config.summarization.max_samples_per_cluster

    labels, fallback = _run_hdbscan_with_fallbacks(
        embeddings,
        reviews,
        pipeline_config.clustering,
    )

    ranked = _rank_clusters(labels, reviews, max_themes)

    if _has_mega_cluster(labels, len(reviews)):
        logger.info("Mega-cluster detected (>80%%); applying rating split fallback")
        split_ranked = _rating_split_clusters(reviews, embeddings, labels, max_themes)
        if len(split_ranked) >= 2:
            ranked = split_ranked
            fallback = fallback or "rating_split_mega"

    for cluster in ranked:
        cluster.samples = select_cluster_samples(
            cluster.indices,
            reviews,
            embeddings,
            max_samples,
            random_state=pipeline_config.clustering.umap.random_state,
        )

    noise_count = int(np.sum(np.array(labels) == -1))
    noise_fraction = noise_count / len(reviews) if reviews else 0.0

    return ClusteringResult(
        labels=list(labels),
        ranked_clusters=ranked,
        noise_count=noise_count,
        noise_fraction=noise_fraction,
        fallback_used=fallback,
    )


def _run_hdbscan_with_fallbacks(
    embeddings: np.ndarray,
    reviews: List[Review],
    clustering_config: ClusteringConfig,
) -> Tuple[np.ndarray, Optional[str]]:
    labels = _fit_hdbscan(embeddings, clustering_config)
    fallback: Optional[str] = None

    if _all_noise(labels):
        logger.warning("All noise after initial HDBSCAN; lowering min_cluster_size")
        lowered = ClusteringConfig(
            umap=clustering_config.umap,
            hdbscan=clustering_config.hdbscan.model_copy(
                update={
                    "min_cluster_size": max(3, clustering_config.hdbscan.min_cluster_size - 2),
                }
            ),
        )
        labels = _fit_hdbscan(embeddings, lowered)
        fallback = "lowered_min_cluster_size"

    if _all_noise(labels):
        logger.warning("Still all noise; using rating-stratified synthetic clusters")
        labels = _rating_stratified_labels(reviews)
        fallback = "rating_stratified"

    return labels, fallback


def _fit_hdbscan(embeddings: np.ndarray, clustering_config: ClusteringConfig) -> np.ndarray:
    umap_cfg = clustering_config.umap
    hdb_cfg = clustering_config.hdbscan

    reducer = umap.UMAP(
        n_neighbors=umap_cfg.n_neighbors,
        n_components=umap_cfg.n_components,
        metric=umap_cfg.metric,
        random_state=umap_cfg.random_state,
    )
    reduced = reducer.fit_transform(embeddings)

    clusterer = hdbscan.HDBSCAN(
        min_cluster_size=hdb_cfg.min_cluster_size,
        min_samples=hdb_cfg.min_samples,
    )
    return clusterer.fit_predict(reduced)


def _all_noise(labels: np.ndarray) -> bool:
    unique = set(labels.tolist())
    return unique == {-1} or len(unique) == 0


def _has_mega_cluster(labels: np.ndarray, total: int) -> bool:
    if total == 0:
        return False
    labels_arr = np.array(labels)
    for label in set(labels_arr.tolist()):
        if label == -1:
            continue
        if int(np.sum(labels_arr == label)) / total > MEGA_CLUSTER_FRACTION:
            return True
    return False


def _rating_stratified_labels(reviews: List[Review]) -> np.ndarray:
    """Assign synthetic cluster ids: low (1-2★), mid (3★), high (4-5★)."""
    labels = np.full(len(reviews), -1, dtype=int)
    low = [i for i, r in enumerate(reviews) if r.rating <= 2]
    mid = [i for i, r in enumerate(reviews) if r.rating == 3]
    high = [i for i, r in enumerate(reviews) if r.rating >= 4]

    if len(low) >= 3:
        for i in low:
            labels[i] = 0
    if len(mid) >= 3:
        for i in mid:
            labels[i] = 1
    if len(high) >= 3:
        for i in high:
            labels[i] = 2

    return labels


def _rating_split_clusters(
    reviews: List[Review],
    embeddings: np.ndarray,
    labels: np.ndarray,
    max_themes: int,
) -> List[RankedCluster]:
    """Split the largest cluster by low vs high rating."""
    labels_arr = np.array(labels)
    cluster_sizes = {
        label: int(np.sum(labels_arr == label))
        for label in set(labels_arr.tolist())
        if label != -1
    }
    if not cluster_sizes:
        return []

    mega_label = max(cluster_sizes, key=cluster_sizes.get)
    mega_indices = [i for i, label in enumerate(labels_arr.tolist()) if label == mega_label]

    low_idx = [i for i in mega_indices if reviews[i].rating <= 2]
    high_idx = [i for i in mega_indices if reviews[i].rating >= 4]

    synthetic_labels = labels_arr.copy()
    if len(low_idx) >= 3:
        for i in low_idx:
            synthetic_labels[i] = 1000
    if len(high_idx) >= 3:
        for i in high_idx:
            synthetic_labels[i] = 1001

    return _rank_clusters(synthetic_labels.tolist(), reviews, max_themes)


def _rank_clusters(
    labels: List[int],
    reviews: List[Review],
    max_themes: int,
) -> List[RankedCluster]:
    labels_arr = np.array(labels)
    clusters: List[RankedCluster] = []

    for label in sorted(set(labels)):
        if label == -1:
            continue
        indices = [i for i, lbl in enumerate(labels_arr.tolist()) if lbl == label]
        if not indices:
            continue
        ratings = [reviews[i].rating for i in indices]
        avg_rating = sum(ratings) / len(ratings)
        size = len(indices)
        score = size * (6.0 - avg_rating)
        clusters.append(
            RankedCluster(
                label=int(label),
                indices=indices,
                size=size,
                avg_rating=avg_rating,
                score=score,
            )
        )

    clusters.sort(key=lambda c: (-c.score, -c.size, c.avg_rating))
    return clusters[:max_themes]


def select_cluster_samples(
    indices: List[int],
    reviews: List[Review],
    embeddings: np.ndarray,
    max_samples: int,
    *,
    random_state: int = 42,
) -> List[Review]:
    """Pick medoid + diverse samples from cluster members."""
    if not indices:
        return []
    if len(indices) <= max_samples:
        return [reviews[i] for i in indices]

    cluster_embeddings = embeddings[indices]
    centroid = cluster_embeddings.mean(axis=0, keepdims=True)
    dist_to_centroid = cosine_distances(cluster_embeddings, centroid).reshape(-1)
    medoid_local = int(np.argmin(dist_to_centroid))
    medoid_global = indices[medoid_local]

    selected_locals = [medoid_local]
    remaining_locals = [i for i in range(len(indices)) if i != medoid_local]

    while len(selected_locals) < max_samples and remaining_locals:
        best_local = None
        best_min_dist = -1.0

        for local_idx in remaining_locals:
            dists = cosine_distances(
                cluster_embeddings[local_idx : local_idx + 1],
                cluster_embeddings[selected_locals],
            )
            min_dist = float(dists.min())
            if min_dist > best_min_dist:
                best_min_dist = min_dist
                best_local = local_idx

        if best_local is None:
            rng = np.random.default_rng(random_state + len(selected_locals))
            best_local = int(rng.choice(remaining_locals))
        selected_locals.append(best_local)
        remaining_locals.remove(best_local)

    return [reviews[indices[i]] for i in selected_locals]
