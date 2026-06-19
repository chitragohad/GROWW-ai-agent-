"""Ingestion test fixtures."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List

import pytest

from pulse.ingestion.models import RawReview


@pytest.fixture
def fixtures_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "fixtures"


@pytest.fixture
def sample_scraper_items(fixtures_dir: Path) -> List[dict]:
    with (fixtures_dir / "scraper_reviews.json").open(encoding="utf-8") as handle:
        items = json.load(handle)
    for item in items:
        item["at"] = datetime.fromisoformat(item["at"])
    return items


@pytest.fixture
def sample_raw_reviews(sample_scraper_items: List[dict]) -> List[RawReview]:
    reviews: List[RawReview] = []
    for item in sample_scraper_items:
        reviews.append(
            RawReview(
                text=item["content"],
                rating=int(item["score"]),
                published_at=item["at"].astimezone(timezone.utc),
                package_id="com.nextbillion.groww",
                review_id=item.get("reviewId"),
            )
        )
    return reviews
