"""Normalizer and deduplication tests."""

from datetime import datetime, timezone

from pulse.ingestion.models import RawReview
from pulse.ingestion.normalizer import (
    contains_emoji,
    dedupe_raw_reviews,
    is_english,
    normalize_reviews,
    passes_normalization_filters,
    word_count,
)


def _raw(text: str, rating: int = 3, review_id: str = "r1") -> RawReview:
    return RawReview(
        text=text,
        rating=rating,
        published_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
        review_id=review_id,
    )


def test_word_count():
    assert word_count("one two three four five six seven eight") == 8


def test_contains_emoji_detects_unicode_emoji():
    assert contains_emoji("This app is bad 😀 during market hours")


def test_is_english_rejects_hindi_script():
    text = "यह ऐप बहुत खराब है और कभी कभी क्रैश हो जाता है बार बार हमेशा"
    assert is_english(text) is False


def test_is_english_accepts_plain_english():
    text = "The app freezes during market hours and support is very slow to respond"
    assert is_english(text) is True


def test_passes_normalization_filters_order():
    short = passes_normalization_filters("too short")
    assert short == (False, "short")

    emoji_text = "This app is terrible 😀 during market open hours every single day lately"
    assert passes_normalization_filters(emoji_text) == (False, "emoji")

    hindi = "यह ऐप बहुत खराब है और कभी कभी क्रैश हो जाता है बार बार हमेशा"
    assert passes_normalization_filters(hindi) == (False, "language")


def test_dedupe_raw_reviews(sample_raw_reviews):
    deduped = dedupe_raw_reviews(sample_raw_reviews)
    assert len(deduped) == len(sample_raw_reviews) - 1


def test_normalize_rejects_short_reviews():
    normalized, stats = normalize_reviews([_raw("too short")], min_words=8)
    assert normalized == []
    assert stats["dropped_short"] == 1


def test_normalize_rejects_emoji_reviews():
    text = "This app is terrible 😀 during market open hours every single day lately"
    normalized, stats = normalize_reviews([_raw(text)], min_words=8)
    assert normalized == []
    assert stats["dropped_emoji"] == 1


def test_normalize_rejects_hindi_only_reviews():
    text = "यह ऐप बहुत खराब है और कभी कभी क्रैश हो जाता है बार बार हमेशा"
    normalized, stats = normalize_reviews([_raw(text)], min_words=8)
    assert normalized == []
    assert stats["dropped_language"] == 1


def test_normalize_keeps_english_reviews_without_emoji(sample_raw_reviews):
    normalized, stats = normalize_reviews(sample_raw_reviews, min_words=8)
    assert stats["normalized_count"] >= 3
    assert all(len(review.text.split()) >= 8 for review in normalized)
    assert all(not contains_emoji(review.text) for review in normalized)
    assert all(is_english(review.text) for review in normalized)
