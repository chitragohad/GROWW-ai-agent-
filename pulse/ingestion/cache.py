"""Disk cache for raw and normalized review pulls."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import List, Literal, Optional

from pydantic import BaseModel, Field

from pulse.ingestion.models import RawReview, Review

MANIFEST_FILE = "manifest.json"
RAW_FILE = "reviews_raw.json"
NORMALIZED_FILE = "reviews_normalized.json"


class CacheManifest(BaseModel):
    status: Literal["success", "error"]
    product: str
    package_id: str
    cache_date: str
    window_weeks: int
    window_start: datetime
    window_end: datetime
    scraped_at: Optional[datetime] = None
    raw_count: int = 0
    normalized_count: int = 0
    filter_stats: dict = Field(default_factory=dict)
    error_message: Optional[str] = None
    scrape_failed_at: Optional[datetime] = None
    from_cache: bool = False


def cache_dir_for(product: str, cache_date: Optional[date] = None, *, data_dir: Path) -> Path:
    day = cache_date or datetime.now(timezone.utc).date()
    return data_dir / "cache" / product / day.isoformat()


def manifest_path(product: str, *, data_dir: Path, cache_date: Optional[date] = None) -> Path:
    return cache_dir_for(product, cache_date, data_dir=data_dir) / MANIFEST_FILE


def load_manifest(
    product: str,
    *,
    data_dir: Path,
    cache_date: Optional[date] = None,
) -> Optional[CacheManifest]:
    path = manifest_path(product, data_dir=data_dir, cache_date=cache_date)
    if not path.is_file():
        return None
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    return CacheManifest.model_validate(data)


def load_cached_reviews(
    product: str,
    *,
    data_dir: Path,
    cache_date: Optional[date] = None,
) -> tuple[List[RawReview], List[Review], CacheManifest]:
    """Load a successful cache entry; raise if missing or not successful."""
    directory = cache_dir_for(product, cache_date, data_dir=data_dir)
    manifest = load_manifest(product, data_dir=data_dir, cache_date=cache_date)
    if manifest is None:
        raise FileNotFoundError(f"No cache manifest for {product}")
    if manifest.status != "success":
        raise ValueError(f"Cache for {product} is not successful: {manifest.status}")

    raw = _load_model_list(directory / RAW_FILE, RawReview)
    normalized = _load_model_list(directory / NORMALIZED_FILE, Review)
    manifest.from_cache = True
    return raw, normalized, manifest


def is_cache_valid(
    product: str,
    *,
    data_dir: Path,
    window_weeks: int,
    cache_date: Optional[date] = None,
) -> bool:
    manifest = load_manifest(product, data_dir=data_dir, cache_date=cache_date)
    if manifest is None or manifest.status != "success":
        return False
    directory = cache_dir_for(product, cache_date, data_dir=data_dir)
    return (
        manifest.window_weeks == window_weeks
        and (directory / RAW_FILE).is_file()
        and (directory / NORMALIZED_FILE).is_file()
    )


def write_error_manifest(
    product: str,
    *,
    data_dir: Path,
    package_id: str,
    window_weeks: int,
    window_start: datetime,
    window_end: datetime,
    error_message: str,
    cache_date: Optional[date] = None,
) -> CacheManifest:
    """Record a failed ingestion without writing partial review files."""
    directory = cache_dir_for(product, cache_date, data_dir=data_dir)
    directory.mkdir(parents=True, exist_ok=True)
    _remove_partial_files(directory)

    manifest = CacheManifest(
        status="error",
        product=product,
        package_id=package_id,
        cache_date=(cache_date or datetime.now(timezone.utc).date()).isoformat(),
        window_weeks=window_weeks,
        window_start=window_start,
        window_end=window_end,
        error_message=error_message,
        scrape_failed_at=datetime.now(timezone.utc),
    )
    _write_json(directory / MANIFEST_FILE, manifest.model_dump(mode="json"))
    return manifest


def write_success_cache(
    product: str,
    *,
    data_dir: Path,
    package_id: str,
    window_weeks: int,
    window_start: datetime,
    window_end: datetime,
    raw_reviews: List[RawReview],
    normalized_reviews: List[Review],
    filter_stats: dict,
    cache_date: Optional[date] = None,
) -> CacheManifest:
    """Write raw, normalized, and manifest files for a successful pull."""
    directory = cache_dir_for(product, cache_date, data_dir=data_dir)
    directory.mkdir(parents=True, exist_ok=True)

    _write_json(directory / RAW_FILE, [r.model_dump(mode="json") for r in raw_reviews])
    _write_json(
        directory / NORMALIZED_FILE,
        [r.model_dump(mode="json") for r in normalized_reviews],
    )
    manifest = CacheManifest(
        status="success",
        product=product,
        package_id=package_id,
        cache_date=(cache_date or datetime.now(timezone.utc).date()).isoformat(),
        window_weeks=window_weeks,
        window_start=window_start,
        window_end=window_end,
        scraped_at=datetime.now(timezone.utc),
        raw_count=len(raw_reviews),
        normalized_count=len(normalized_reviews),
        filter_stats=filter_stats,
    )
    _write_json(directory / MANIFEST_FILE, manifest.model_dump(mode="json"))
    return manifest


def _remove_partial_files(directory: Path) -> None:
    for name in (RAW_FILE, NORMALIZED_FILE):
        path = directory / name
        if path.exists():
            path.unlink()


def _write_json(path: Path, payload: object) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)


def _load_model_list(path: Path, model: type) -> list:
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, list):
        raise ValueError(f"Expected list in {path}")
    return [model.model_validate(item) for item in data]
