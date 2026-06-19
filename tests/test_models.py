"""Core model tests."""

from datetime import datetime, timezone

from pulse.ingestion.models import PulseReport, RawReview, Review, RunContext, Theme


def test_review_models():
    raw = RawReview(
        text="The app freezes when the market opens.",
        rating=1,
        published_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
        package_id="com.nextbillion.groww",
    )
    review = Review(text=raw.text, rating=raw.rating)
    assert review.rating == 1
    payload = review.model_dump(mode="json")
    assert set(payload.keys()) == {"text", "rating"}


def test_run_context():
    ctx = RunContext(
        run_id="groww-2026-W23-abc",
        product="groww",
        iso_week="2026-W23",
        window_weeks=10,
    )
    assert ctx.dry_run is False
    assert ctx.email_mode == "draft"


def test_pulse_report():
    report = PulseReport(
        product="groww",
        display_name="Groww",
        iso_week="2026-W23",
        window_weeks=10,
        review_count=872,
        generated_at=datetime.now(timezone.utc),
        themes=[
            Theme(
                theme_name="App performance",
                summary="Crashes during trading hours.",
                quotes=["The app freezes exactly when the market opens."],
            )
        ],
    )
    assert len(report.themes) == 1
    assert report.source == "google_play"
