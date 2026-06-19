"""PII scrubbing before embedding, LLM calls, and publishing."""

from __future__ import annotations

import re
from typing import List, Tuple

from pulse.ingestion.models import Review

EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
PHONE_PATTERN = re.compile(r"(?:\+91[\s-]?)?[6-9]\d{9}\b")
LONG_NUMERIC_PATTERN = re.compile(r"\b\d{10,}\b")
URL_PATTERN = re.compile(r"https?://[^\s]+|www\.[^\s]+", re.IGNORECASE)


def scrub_text(text: str) -> Tuple[str, dict]:
    """Redact PII patterns; keep financial amounts. Returns scrubbed text and redaction counts."""
    counts = {"email": 0, "phone": 0, "id": 0, "url": 0}
    scrubbed = text

    scrubbed, n = EMAIL_PATTERN.subn("[EMAIL]", scrubbed)
    counts["email"] += n

    scrubbed, n = PHONE_PATTERN.subn("[PHONE]", scrubbed)
    counts["phone"] += n

    scrubbed, n = LONG_NUMERIC_PATTERN.subn("[ID]", scrubbed)
    counts["id"] += n

    def _redact_url(match: re.Match) -> str:
        counts["url"] += 1
        return "[URL]"

    scrubbed = URL_PATTERN.sub(_redact_url, scrubbed)
    return scrubbed.strip(), counts


def scrub_reviews(reviews: List[Review]) -> Tuple[List[Review], dict]:
    """Return scrubbed reviews and aggregate redaction stats."""
    scrubbed: List[Review] = []
    totals = {"email": 0, "phone": 0, "id": 0, "url": 0}
    for review in reviews:
        text, counts = scrub_text(review.text)
        for key, value in counts.items():
            totals[key] += value
        scrubbed.append(Review(text=text, rating=review.rating))
    return scrubbed, totals
