"""Ingestion service orchestration tests."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional

import pytest

from pulse.ingestion.models import RawReview
from pulse.ingestion.play_store import PlayStoreScrapeError
from pulse.ingestion.service import run_ingestion


class MockReviewSource:
    def __init__(self, reviews: List[RawReview], *, fail: bool = False) -> None:
        self.reviews = reviews
        self.fail = fail
        self.calls = 0

    def fetch_reviews(
        self,
        *,
        package_id: str,
        since: datetime,
        max_reviews: int,
        lang: str = "en",
        country: str = "in",
    ) -> List[RawReview]:
        self.calls += 1
        if self.fail:
            raise PlayStoreScrapeError("mock scrape failure")
        return [r for r in self.reviews if r.published_at >= since][:max_reviews]


def _english_review(text: str, day: int, review_id: str) -> RawReview:
    return RawReview(
        text=text,
        rating=2,
        published_at=datetime(2026, 5, day, tzinfo=timezone.utc),
        package_id="com.nextbillion.groww",
        review_id=review_id,
    )


def _make_reviews(count: int) -> List[RawReview]:
    template = (
        "The app freezes during market hours and support is very slow to respond always"
    )
    return [
        _english_review(f"{template} number {index}", (index % 28) + 1, f"r-{index}")
        for index in range(count)
    ]


def test_run_ingestion_writes_cache(tmp_path: Path):
    source = MockReviewSource(_make_reviews(25))
    result = run_ingestion(
        "groww",
        weeks_back=10,
        force_refresh=True,
        data_dir=tmp_path,
        source=source,
    )
    assert result.manifest.status == "success"
    assert result.manifest.raw_count == 25
    assert result.manifest.normalized_count >= 20
    assert source.calls == 1


def test_run_ingestion_cache_hit_skips_scrape(tmp_path: Path):
    source = MockReviewSource(_make_reviews(25))
    run_ingestion(
        "groww",
        weeks_back=10,
        force_refresh=True,
        data_dir=tmp_path,
        source=source,
    )
    source.calls = 0
    cached = run_ingestion(
        "groww",
        weeks_back=10,
        force_refresh=False,
        data_dir=tmp_path,
        source=source,
    )
    assert cached.manifest.from_cache is True
    assert source.calls == 0


def test_run_ingestion_failure_writes_error_manifest_only(tmp_path: Path):
    source = MockReviewSource([], fail=True)
    with pytest.raises(PlayStoreScrapeError):
        run_ingestion(
            "groww",
            weeks_back=10,
            force_refresh=True,
            data_dir=tmp_path,
            source=source,
        )

    cache_dir = tmp_path / "cache" / "groww"
    day_dirs = list(cache_dir.iterdir())
    assert len(day_dirs) == 1
    day_dir = day_dirs[0]
    assert (day_dir / "manifest.json").is_file()
    assert not (day_dir / "reviews_raw.json").exists()
