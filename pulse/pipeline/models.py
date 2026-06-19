"""Pipeline-internal models for clustering and analysis."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from pulse.ingestion.models import Review, Theme


@dataclass
class RankedCluster:
    label: int
    indices: List[int]
    size: int
    avg_rating: float
    score: float
    samples: List[Review] = field(default_factory=list)


@dataclass
class ClusteringResult:
    labels: List[int]
    ranked_clusters: List[RankedCluster]
    noise_count: int
    noise_fraction: float
    fallback_used: Optional[str] = None


@dataclass
class GroqUsageStats:
    requests: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    re_prompts: int = 0

    @property
    def total_tokens(self) -> int:
        return self.tokens_in + self.tokens_out


@dataclass
class AnalysisResult:
    themes: List[Theme]
    clustering: ClusteringResult
    groq_usage: Optional[GroqUsageStats] = None
    scrub_stats: Optional[dict] = None
