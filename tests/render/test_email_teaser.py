"""Email teaser rendering tests."""

from __future__ import annotations

from datetime import datetime, timezone

from pulse.ingestion.models import PulseReport, Theme
from pulse.render.email_teaser import render_email_teaser
from tests.render.conftest import load_golden


def test_email_teaser_matches_golden_text(sample_report: PulseReport, golden_dir) -> None:
    teaser = render_email_teaser(sample_report)
    assert teaser.text_body == load_golden("email_text.txt", golden_dir)


def test_email_teaser_matches_golden_html(sample_report: PulseReport, golden_dir) -> None:
    teaser = render_email_teaser(sample_report)
    assert teaser.html_body == load_golden("email_html.html", golden_dir)


def test_email_teaser_uses_deep_link_when_provided(sample_report: PulseReport) -> None:
    link = "https://docs.google.com/document/d/abc123#heading=h.xyz"
    teaser = render_email_teaser(sample_report, deep_link=link)
    assert link in teaser.html_body
    assert link in teaser.text_body
    assert teaser.deep_link == link


def test_email_escapes_html_special_chars() -> None:
    report = PulseReport(
        product="groww",
        display_name="Groww",
        iso_week="2026-W23",
        window_weeks=10,
        review_count=10,
        generated_at=datetime(2026, 6, 8, 10, 30, tzinfo=timezone.utc),
        themes=[
            Theme(
                theme_name="Bug <script>",
                summary="App & support issues",
                quotes=["quote"],
            )
        ],
    )
    teaser = render_email_teaser(report)
    assert "<script>" not in teaser.html_body
    assert "&lt;script&gt;" in teaser.html_body
    assert "App &amp; support" in teaser.html_body


def test_email_contains_theme_bullets_only_not_full_report(sample_report: PulseReport) -> None:
    teaser = render_email_teaser(sample_report)
    assert "Real user quotes" not in teaser.text_body
    assert sample_report.themes[0].quotes[0] not in teaser.text_body
    assert sample_report.themes[0].theme_name in teaser.text_body
