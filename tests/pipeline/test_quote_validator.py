"""Quote validation against source review text."""

from __future__ import annotations

from pulse.pipeline.quote_validator import quote_in_source, validate_quotes


def test_exact_substring_match() -> None:
    source = "The app crashes every time I open mutual funds section"
    assert quote_in_source("crashes every time I open", source)


def test_case_insensitive_match() -> None:
    source = "Withdrawal failed twice this week"
    assert quote_in_source("withdrawal failed", source)


def test_ellipsis_prefix_match() -> None:
    source = "Customer support never responds to my tickets about KYC"
    assert quote_in_source("Customer support never responds...", source)


def test_hallucinated_quote_rejected() -> None:
    source = "Slow loading charts during market hours"
    assert not quote_in_source("App stole my money", source)


def test_validate_quotes_splits_valid_invalid() -> None:
    sources = ["Payment stuck pending for three days now"]
    valid, invalid = validate_quotes(
        ["Payment stuck pending", "Completely made up quote"],
        sources,
    )
    assert len(valid) == 1
    assert len(invalid) == 1
