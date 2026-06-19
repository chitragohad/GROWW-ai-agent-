"""Review normalization and deduplication.

Phase 1 normalization rules (applied in order after deduplication):

1. **Minimum length** — drop reviews with fewer than 8 words.
2. **Emoji or non-English** — drop reviews that contain any emoji, use a
   non-Latin script (e.g. Hindi), or are detected as a language other than English.
"""

from __future__ import annotations

import hashlib
import re
from typing import Iterable, List, Optional, Tuple

from pulse.ingestion.models import RawReview, Review

# Common emoji blocks — any match causes the review to be dropped.
_EMOJI_PATTERN = re.compile(
    "["
    "\U0001F300-\U0001FAFF"
    "\U00002700-\U000027BF"
    "\U0001F600-\U0001F64F"
    "\U00002600-\U000026FF"
    "]+",
    flags=re.UNICODE,
)

# Devanagari and other Indic scripts — treated as non-English.
_NON_LATIN_SCRIPT = re.compile(r"[\u0900-\u097F\u0980-\u09FF\u0A00-\u0A7F\u0A80-\u0AFF]")


def review_dedupe_key(review: RawReview) -> str:
    """Stable hash for deduplication: text + rating + published_at."""
    payload = f"{review.text.strip()}|{review.rating}|{review.published_at.isoformat()}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def dedupe_raw_reviews(reviews: Iterable[RawReview]) -> List[RawReview]:
    """Remove duplicate raw reviews while preserving first-seen order."""
    seen: set[str] = set()
    unique: List[RawReview] = []
    for review in reviews:
        key = review_dedupe_key(review)
        if key in seen:
            continue
        seen.add(key)
        unique.append(review)
    return unique


def word_count(text: str) -> int:
    return len(text.split())


def contains_emoji(text: str) -> bool:
    return _EMOJI_PATTERN.search(text) is not None


def contains_non_latin_script(text: str) -> bool:
    return _NON_LATIN_SCRIPT.search(text) is not None


def is_english(text: str) -> bool:
    """Return True only when the review text is English (Latin script + langdetect)."""
    stripped = text.strip()
    if not stripped:
        return False
    if contains_non_latin_script(stripped):
        return False

    try:
        from langdetect import LangDetectException, detect_langs

        candidates = detect_langs(stripped)
        if not candidates:
            return False
        return candidates[0].lang == "en"
    except LangDetectException:
        return False
    except ImportError:
        # Without langdetect, keep Latin-only text as a best-effort fallback.
        return all(not ch.isalpha() or ch.isascii() for ch in stripped)


def passes_normalization_filters(
    text: str,
    *,
    min_words: int = 8,
) -> Tuple[bool, Optional[str]]:
    """
    Check phase-1 normalization rules.

    Returns (passed, drop_reason) where drop_reason is one of:
    ``short``, ``emoji``, ``language``, or None when passed.
    """
    stripped = text.strip()
    if word_count(stripped) < min_words:
        return False, "short"
    if contains_emoji(stripped):
        return False, "emoji"
    if not is_english(stripped):
        return False, "language"
    return True, None


def normalize_review(
    raw: RawReview,
    *,
    min_words: int = 8,
    allowed_language: str = "en",
) -> Optional[Review]:
    """Apply quality filters; return None when the review should be dropped."""
    if allowed_language != "en":
        raise ValueError(f"Only English normalization is supported in v1, got {allowed_language}")

    text = raw.text.strip()
    passed, _reason = passes_normalization_filters(text, min_words=min_words)
    if not passed:
        return None

    return Review(text=text, rating=raw.rating)


def normalize_reviews(
    raw_reviews: Iterable[RawReview],
    *,
    min_words: int = 8,
    allowed_language: str = "en",
) -> Tuple[List[Review], dict]:
    """
    Deduplicate, filter, and normalize raw reviews.

    Returns normalized reviews and filter stats for the manifest.
    """
    if allowed_language != "en":
        raise ValueError(f"Only English normalization is supported in v1, got {allowed_language}")

    deduped = dedupe_raw_reviews(raw_reviews)
    normalized: List[Review] = []
    dropped_short = 0
    dropped_emoji = 0
    dropped_language = 0

    original_list = list(raw_reviews)
    dropped_duplicates = max(0, len(original_list) - len(deduped))

    for raw in deduped:
        text = raw.text.strip()
        passed, reason = passes_normalization_filters(text, min_words=min_words)
        if not passed:
            if reason == "short":
                dropped_short += 1
            elif reason == "emoji":
                dropped_emoji += 1
            elif reason == "language":
                dropped_language += 1
            continue

        normalized.append(Review(text=text, rating=raw.rating))

    stats = {
        "raw_input_count": len(original_list),
        "raw_unique_count": len(deduped),
        "dropped_duplicates": dropped_duplicates,
        "dropped_short": dropped_short,
        "dropped_emoji": dropped_emoji,
        "dropped_language": dropped_language,
        "normalized_count": len(normalized),
    }
    return normalized, stats
