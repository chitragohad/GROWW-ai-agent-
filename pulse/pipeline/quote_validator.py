"""Validate LLM quotes against source review text."""

from __future__ import annotations

import re
from typing import List, Tuple


def _normalize(text: str) -> str:
    collapsed = re.sub(r"\s+", " ", text.strip().lower())
    return collapsed


def quote_in_source(quote: str, source_text: str) -> bool:
    """Check quote is a substring of source (case-insensitive, whitespace-normalized)."""
    norm_quote = _normalize(quote)
    norm_source = _normalize(source_text)
    if not norm_quote:
        return False
    if norm_quote in norm_source:
        return True
    if norm_quote.endswith("..."):
        prefix = norm_quote[:-3].strip()
        if prefix and prefix in norm_source:
            return True
    return False


def validate_quotes(
    quotes: List[str],
    source_texts: List[str],
) -> Tuple[List[str], List[str]]:
    """
    Return (valid_quotes, invalid_quotes).
    A quote is valid if it appears in any source text.
    """
    valid: List[str] = []
    invalid: List[str] = []
    for quote in quotes:
        if any(quote_in_source(quote, src) for src in source_texts):
            valid.append(quote)
        else:
            invalid.append(quote)
    return valid, invalid
