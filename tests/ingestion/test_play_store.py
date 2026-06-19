"""Play Store scraper tests with mocked pagination."""

from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple

import pytest

from pulse.ingestion.play_store import PlayStoreScrapeError, PlayStoreScraper, _map_scraper_item


def test_map_scraper_item(sample_scraper_items):
    item = sample_scraper_items[0]
    raw = _map_scraper_item(item, package_id="com.nextbillion.groww")
    assert raw is not None
    assert raw.rating == 1
    assert raw.review_id == "rev-001"


def test_fetch_reviews_paginates_and_filters_by_date(sample_scraper_items):
    calls = {"count": 0}

    def fetch_page(
        package_id: str,
        lang: str,
        country: str,
        count: int,
        continuation_token: Optional[str],
    ) -> Tuple[List[dict], Optional[str]]:
        calls["count"] += 1
        if continuation_token is None:
            return sample_scraper_items[:4], "token-2"
        return sample_scraper_items[4:], None

    scraper = PlayStoreScraper(fetch_page=fetch_page, page_delay_seconds=0)
    since = datetime(2026, 5, 1, tzinfo=timezone.utc)
    reviews = scraper.fetch_reviews(
        package_id="com.nextbillion.groww",
        since=since,
        max_reviews=100,
    )
    assert calls["count"] == 2
    assert len(reviews) == 8
    assert all(review.published_at >= since for review in reviews)


def test_fetch_retries_then_raises():
    attempts = {"count": 0}

    def failing_fetch(*_args, **_kwargs):
        attempts["count"] += 1
        raise ConnectionError("connection timeout while fetching")

    scraper = PlayStoreScraper(
        fetch_page=failing_fetch,
        max_retries=2,
        base_backoff_seconds=0,
        page_delay_seconds=0,
    )
    since = datetime.now(timezone.utc) - timedelta(weeks=10)
    with pytest.raises(PlayStoreScrapeError):
        scraper.fetch_reviews(
            package_id="com.nextbillion.groww",
            since=since,
            max_reviews=10,
        )
    assert attempts["count"] == 3
