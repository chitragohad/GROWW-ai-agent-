"""Review source protocol for multi-platform ingestion."""

from __future__ import annotations

from datetime import datetime
from typing import List, Protocol, runtime_checkable

from pulse.ingestion.models import RawReview


@runtime_checkable
class ReviewSource(Protocol):
    """Fetch public app reviews from a single store/source."""

    def fetch_reviews(
        self,
        *,
        package_id: str,
        since: datetime,
        max_reviews: int,
        lang: str = "en",
        country: str = "in",
    ) -> List[RawReview]:
        """Return raw reviews published on or after ``since``, up to ``max_reviews``."""
