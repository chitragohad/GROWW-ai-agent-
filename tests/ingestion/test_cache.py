"""Cache read/write tests."""

from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from pulse.ingestion.cache import (
    is_cache_valid,
    load_cached_reviews,
    load_manifest,
    write_error_manifest,
    write_success_cache,
)
from pulse.ingestion.models import RawReview, Review


def _raw(text: str) -> RawReview:
    return RawReview(
        text=text,
        rating=2,
        published_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
    )


def _review(text: str) -> Review:
    return Review(text=text, rating=2)


def test_write_success_cache_and_reload(tmp_path: Path):
    raw = [_raw("one two three four five six seven eight")]
    normalized = [_review("one two three four five six seven eight")]
    start = datetime(2026, 3, 1, tzinfo=timezone.utc)
    end = datetime(2026, 6, 1, tzinfo=timezone.utc)
    cache_day = date(2026, 6, 10)

    manifest = write_success_cache(
        "groww",
        data_dir=tmp_path,
        package_id="com.nextbillion.groww",
        window_weeks=10,
        window_start=start,
        window_end=end,
        raw_reviews=raw,
        normalized_reviews=normalized,
        filter_stats={"normalized_count": 1},
        cache_date=cache_day,
    )
    assert manifest.status == "success"
    assert is_cache_valid("groww", data_dir=tmp_path, window_weeks=10, cache_date=cache_day)

    loaded_raw, loaded_norm, loaded_manifest = load_cached_reviews(
        "groww",
        data_dir=tmp_path,
        cache_date=cache_day,
    )
    assert len(loaded_raw) == 1
    assert len(loaded_norm) == 1
    assert loaded_manifest.from_cache is True


def test_write_error_manifest_without_partial_review_files(tmp_path: Path):
    start = datetime(2026, 3, 1, tzinfo=timezone.utc)
    end = datetime(2026, 6, 1, tzinfo=timezone.utc)
    cache_day = date(2026, 6, 10)

    manifest = write_error_manifest(
        "groww",
        data_dir=tmp_path,
        package_id="com.nextbillion.groww",
        window_weeks=10,
        window_start=start,
        window_end=end,
        error_message="scrape failed",
        cache_date=cache_day,
    )
    cache_dir = tmp_path / "cache" / "groww" / cache_day.isoformat()
    assert manifest.status == "error"
    assert (cache_dir / "manifest.json").is_file()
    assert not (cache_dir / "reviews_raw.json").exists()
    assert not (cache_dir / "reviews_normalized.json").exists()

    loaded = load_manifest("groww", data_dir=tmp_path, cache_date=cache_day)
    assert loaded is not None
    assert loaded.error_message == "scrape failed"
