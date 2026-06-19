"""Google Play Store review scraper with pagination and retries."""

from __future__ import annotations

import random
import time
from datetime import datetime, timezone
from typing import Callable, List, Optional, Tuple

from pulse.ingestion.models import RawReview
from pulse.ingestion.sources import ReviewSource
from pulse.logging import get_logger, log_event

logger = get_logger("pulse.ingestion.play_store")

# Retryable error fragments from google-play-scraper / HTTP layer.
_RETRYABLE_MARKERS = (
    "429",
    "too many requests",
    "timeout",
    "timed out",
    "connection",
    "503",
    "502",
    "500",
    "temporarily unavailable",
)


class PlayStoreScrapeError(Exception):
    """Raised when Play Store scraping fails after retries."""


class PlayStoreScraper(ReviewSource):
    """Fetch public Play Store reviews via google-play-scraper."""

    def __init__(
        self,
        *,
        page_size: int = 200,
        page_delay_seconds: float = 0.75,
        max_retries: int = 3,
        base_backoff_seconds: float = 1.0,
        fetch_page: Optional[Callable[..., Tuple[List[dict], Optional[str]]]] = None,
    ) -> None:
        self.page_size = page_size
        self.page_delay_seconds = page_delay_seconds
        self.max_retries = max_retries
        self.base_backoff_seconds = base_backoff_seconds
        self._fetch_page = fetch_page or self._default_fetch_page

    def fetch_reviews(
        self,
        *,
        package_id: str,
        since: datetime,
        max_reviews: int,
        lang: str = "en",
        country: str = "in",
    ) -> List[RawReview]:
        since_utc = _as_utc(since)
        collected: List[RawReview] = []
        continuation_token: Optional[str] = None
        pages = 0

        log_event(
            logger,
            "starting Play Store scrape",
            stage="ingestion",
            context={
                "package_id": package_id,
                "since": since_utc.isoformat(),
                "max_reviews": max_reviews,
                "lang": lang,
                "country": country,
            },
        )

        while len(collected) < max_reviews:
            batch, continuation_token = self._fetch_with_retry(
                package_id=package_id,
                lang=lang,
                country=country,
                continuation_token=continuation_token,
            )
            pages += 1

            if not batch:
                break

            oldest_in_batch: Optional[datetime] = None
            for item in batch:
                raw = _map_scraper_item(item, package_id=package_id)
                if raw is None:
                    continue
                published = _as_utc(raw.published_at)
                oldest_in_batch = published if oldest_in_batch is None else min(oldest_in_batch, published)
                if published >= since_utc:
                    collected.append(raw)
                    if len(collected) >= max_reviews:
                        break

            if len(collected) >= max_reviews:
                break
            if continuation_token is None:
                break
            if oldest_in_batch is not None and oldest_in_batch < since_utc:
                break

            time.sleep(self.page_delay_seconds)

        log_event(
            logger,
            "Play Store scrape completed",
            stage="ingestion",
            context={"package_id": package_id, "pages": pages, "raw_count": len(collected)},
        )
        return collected

    def _fetch_with_retry(
        self,
        *,
        package_id: str,
        lang: str,
        country: str,
        continuation_token: Optional[str],
    ) -> Tuple[List[dict], Optional[str]]:
        last_error: Optional[Exception] = None
        for attempt in range(self.max_retries + 1):
            try:
                return self._fetch_page(
                    package_id,
                    lang,
                    country,
                    self.page_size,
                    continuation_token,
                )
            except Exception as exc:  # noqa: BLE001 — classify retryable scrape errors
                last_error = exc
                if not _is_retryable(exc) or attempt >= self.max_retries:
                    raise PlayStoreScrapeError(str(exc)) from exc
                delay = self.base_backoff_seconds * (2**attempt) + random.uniform(0, 0.25)
                log_event(
                    logger,
                    "Play Store scrape retry",
                    stage="ingestion",
                    context={
                        "attempt": attempt + 1,
                        "delay_seconds": round(delay, 2),
                        "error": str(exc),
                    },
                )
                time.sleep(delay)
        raise PlayStoreScrapeError(str(last_error or "unknown scrape error"))

    @staticmethod
    def _default_fetch_page(
        package_id: str,
        lang: str,
        country: str,
        count: int,
        continuation_token: Optional[str],
    ) -> Tuple[List[dict], Optional[str]]:
        from google_play_scraper import Sort, reviews

        if continuation_token:
            result, token = reviews(package_id, continuation_token=continuation_token)
        else:
            result, token = reviews(
                package_id,
                lang=lang,
                country=country,
                sort=Sort.NEWEST,
                count=count,
            )
        return list(result), token


def _map_scraper_item(item: dict, *, package_id: str) -> Optional[RawReview]:
    text = (item.get("content") or "").strip()
    if not text:
        return None
    rating = item.get("score")
    published = item.get("at")
    if rating is None or published is None:
        return None
    if not isinstance(published, datetime):
        return None
    return RawReview(
        text=text,
        rating=int(rating),
        published_at=_as_utc(published),
        package_id=package_id,
        review_id=item.get("reviewId"),
    )


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _is_retryable(exc: Exception) -> bool:
    message = str(exc).lower()
    return any(marker in message for marker in _RETRYABLE_MARKERS)
