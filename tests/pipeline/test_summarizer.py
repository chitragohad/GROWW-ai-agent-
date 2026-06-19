"""Groq summarizer with mocked client."""

from __future__ import annotations

import json

from pulse.config import load_pipeline_config
from pulse.ingestion.models import Review
from pulse.pipeline.models import RankedCluster
from pulse.pipeline.summarizer import summarize_clusters


class MockGroq:
    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self.calls = 0

    def complete(self, prompt: str, max_output_tokens: int) -> tuple[str, int, int]:
        self.calls += 1
        text = self._responses.pop(0)
        return text, len(prompt) // 4, len(text) // 4


def _cluster_with_samples() -> RankedCluster:
    samples = [
        Review(text="Withdrawal stuck pending for three days without update", rating=1),
        Review(text="Money not credited after selling shares yesterday evening", rating=2),
    ]
    return RankedCluster(
        label=1,
        indices=[0, 1],
        size=10,
        avg_rating=1.5,
        score=45.0,
        samples=samples,
    )


def test_summarizer_accepts_valid_quotes() -> None:
    payload = json.dumps(
        {
            "theme_name": "Withdrawal delays",
            "summary": "Users report stuck withdrawals.",
            "quotes": ["Withdrawal stuck pending for three days"],
            "action_ideas": [{"title": "Fix payout SLA", "detail": "Investigate settlement queue"}],
        }
    )
    client = MockGroq([payload])
    config = load_pipeline_config().summarization

    themes, stats = summarize_clusters([_cluster_with_samples()], config, groq_client=client)

    assert len(themes) == 1
    assert themes[0].theme_name == "Withdrawal delays"
    assert stats.requests == 1


def test_summarizer_drops_hallucinated_quotes_after_retry() -> None:
    bad = json.dumps(
        {
            "theme_name": "Fake issue",
            "summary": "Made up.",
            "quotes": ["This quote does not exist in reviews"],
            "action_ideas": [],
        }
    )
    good = json.dumps(
        {
            "theme_name": "Withdrawal delays",
            "summary": "Users report stuck withdrawals.",
            "quotes": ["Money not credited after selling shares"],
            "action_ideas": [],
        }
    )
    client = MockGroq([bad, good])
    config = load_pipeline_config().summarization
    config = config.model_copy(update={"request_interval_seconds": 0})

    themes, stats = summarize_clusters([_cluster_with_samples()], config, groq_client=client)

    assert len(themes) == 1
    assert stats.re_prompts == 1
    assert stats.requests == 2


def test_summarizer_respects_token_budget() -> None:
    payload = json.dumps(
        {
            "theme_name": "Theme",
            "summary": "Summary",
            "quotes": ["Withdrawal stuck pending for three days"],
            "action_ideas": [],
        }
    )
    client = MockGroq([payload] * 10)
    config = load_pipeline_config().summarization
    config = config.model_copy(update={"max_tokens_per_run": 50, "request_interval_seconds": 0})
    clusters = [_cluster_with_samples() for _ in range(5)]

    themes, stats = summarize_clusters(clusters, config, groq_client=client)

    assert len(themes) < 5
    assert stats.total_tokens <= 50
