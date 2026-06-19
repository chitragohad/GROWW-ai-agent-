"""Ingestion orchestration: scrape → normalize → cache."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional

from pulse.config import ProductConfig, load_product_config
from pulse.ingestion.cache import (
    CacheManifest,
    is_cache_valid,
    load_cached_reviews,
    write_error_manifest,
    write_success_cache,
)
from pulse.ingestion.models import RawReview, Review
from pulse.ingestion.normalizer import normalize_reviews
from pulse.ingestion.play_store import PlayStoreScrapeError, PlayStoreScraper
from pulse.ingestion.sources import ReviewSource
from pulse.logging import get_logger, log_event

logger = get_logger("pulse.ingestion.service")


@dataclass
class IngestionResult:
    product: str
    raw_reviews: List[RawReview]
    normalized_reviews: List[Review]
    manifest: CacheManifest


def compute_review_window(*, window_weeks: int, as_of: Optional[datetime] = None) -> tuple[datetime, datetime]:
    end = as_of or datetime.now(timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    start = end - timedelta(weeks=window_weeks)
    return start, end


def run_ingestion(
    product: str,
    *,
    weeks_back: Optional[int] = None,
    force_refresh: bool = False,
    data_dir: Path,
    source: Optional[ReviewSource] = None,
    cache_date: Optional[datetime] = None,
) -> IngestionResult:
    """
    Fetch, normalize, and cache Play Store reviews for a product.

    Returns cached data on cache hit unless ``force_refresh`` is True.
    """
    product_config = load_product_config(product)
    window_weeks = weeks_back or product_config.ingestion.window_weeks
    if not 8 <= window_weeks <= 12:
        raise ValueError(f"window_weeks must be between 8 and 12, got {window_weeks}")

    cache_day = (cache_date or datetime.now(timezone.utc)).date()
    package_id = product_config.play_store.app_id
    window_start, window_end = compute_review_window(window_weeks=window_weeks)

    if not force_refresh and is_cache_valid(
        product,
        data_dir=data_dir,
        window_weeks=window_weeks,
        cache_date=cache_day,
    ):
        raw, normalized, manifest = load_cached_reviews(
            product,
            data_dir=data_dir,
            cache_date=cache_day,
        )
        log_event(
            logger,
            "ingestion cache hit",
            stage="ingestion",
            context={"product": product, "cache_date": cache_day.isoformat()},
        )
        return IngestionResult(
            product=product,
            raw_reviews=raw,
            normalized_reviews=normalized,
            manifest=manifest,
        )

    scraper = source or PlayStoreScraper()
    try:
        raw_reviews = scraper.fetch_reviews(
            package_id=package_id,
            since=window_start,
            max_reviews=product_config.ingestion.max_reviews,
            lang=product_config.ingestion.allowed_language,
        )
        normalized_reviews, filter_stats = normalize_reviews(
            raw_reviews,
            min_words=product_config.ingestion.min_words,
            allowed_language=product_config.ingestion.allowed_language,
        )
        manifest = write_success_cache(
            product,
            data_dir=data_dir,
            package_id=package_id,
            window_weeks=window_weeks,
            window_start=window_start,
            window_end=window_end,
            raw_reviews=raw_reviews,
            normalized_reviews=normalized_reviews,
            filter_stats=filter_stats,
            cache_date=cache_day,
        )
        log_event(
            logger,
            "ingestion completed",
            stage="ingestion",
            context={
                "product": product,
                "raw_count": manifest.raw_count,
                "normalized_count": manifest.normalized_count,
                "filter_stats": filter_stats,
            },
        )
        return IngestionResult(
            product=product,
            raw_reviews=raw_reviews,
            normalized_reviews=normalized_reviews,
            manifest=manifest,
        )
    except Exception as exc:
        write_error_manifest(
            product,
            data_dir=data_dir,
            package_id=package_id,
            window_weeks=window_weeks,
            window_start=window_start,
            window_end=window_end,
            error_message=str(exc),
            cache_date=cache_day,
        )
        log_event(
            logger,
            "ingestion failed",
            stage="ingestion",
            context={"product": product, "error": str(exc)},
        )
        if isinstance(exc, PlayStoreScrapeError):
            raise
        raise PlayStoreScrapeError(str(exc)) from exc


def validate_ingestion_result(result: IngestionResult, product_config: ProductConfig) -> None:
    """Raise when normalized review count is below configured minimum."""
    minimum = product_config.ingestion.min_reviews
    count = len(result.normalized_reviews)
    if count < minimum:
        raise ValueError(
            f"Normalized review count {count} is below minimum {minimum} for {result.product}"
        )
