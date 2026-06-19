"""Table-driven PII scrubber tests."""

from __future__ import annotations

import pytest

from pulse.ingestion.models import Review
from pulse.pipeline.scrubber import scrub_reviews, scrub_text


@pytest.mark.parametrize(
    "text,expected_fragment",
    [
        ("Contact me at user@example.com for help", "[EMAIL]"),
        ("Call +91 9876543210 about my account", "[PHONE]"),
        ("My aadhaar is 123456789012 in the app", "[ID]"),
        ("Visit https://evil.com/steal?token=abc", "[URL]"),
        ("Lost ₹50000 in a bad trade on Groww", "₹50000"),
        ("Made 2 lakh profit this quarter", "2 lakh"),
    ],
)
def test_scrub_text_patterns(text: str, expected_fragment: str) -> None:
    scrubbed, counts = scrub_text(text)
    assert expected_fragment in scrubbed
    if expected_fragment.startswith("["):
        assert sum(counts.values()) >= 1


def test_scrub_reviews_preserves_rating() -> None:
    reviews = [Review(text="Email me at a@b.co please fix bugs", rating=2)]
    scrubbed, stats = scrub_reviews(reviews)
    assert scrubbed[0].rating == 2
    assert "[EMAIL]" in scrubbed[0].text
    assert stats["email"] == 1
