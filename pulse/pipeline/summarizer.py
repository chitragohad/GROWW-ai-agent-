"""Groq LLM theme summarization with token budget and quote validation."""

from __future__ import annotations

import json
import logging
import os
import time
from typing import List, Optional, Protocol

from pulse.config import SummarizationConfig
from pulse.ingestion.models import ActionIdea, Review, Theme
from pulse.pipeline.models import GroqUsageStats, RankedCluster
from pulse.pipeline.quote_validator import validate_quotes

logger = logging.getLogger(__name__)

THEME_PROMPT = """You are analyzing Google Play Store reviews for a fintech app.
Given sample reviews from one cluster, produce a JSON object with:
- "theme_name": short title (max 8 words)
- "summary": 2-3 sentences describing the user pain or praise
- "quotes": array of 2-3 verbatim quotes copied EXACTLY from the reviews below
- "action_ideas": array of 1-2 objects with "title" and "detail"

Rules:
- Quotes MUST be exact substrings from the provided reviews (no paraphrasing).
- Do not invent product features or issues not supported by the reviews.
- Focus on actionable product feedback.

Reviews:
{reviews}
"""


class GroqClient(Protocol):
    def complete(self, prompt: str, max_output_tokens: int) -> tuple[str, int, int]:
        """Return (text, tokens_in, tokens_out)."""


class SummarizationError(Exception):
    pass


def _format_reviews(samples: List[Review]) -> str:
    lines = []
    for i, review in enumerate(samples, 1):
        lines.append(f"{i}. [{review.rating}★] {review.text}")
    return "\n".join(lines)


def _parse_theme_response(raw: str, cluster: RankedCluster) -> Theme:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SummarizationError(f"Invalid JSON from Groq: {exc}") from exc

    action_ideas = [
        ActionIdea(title=item.get("title", ""), detail=item.get("detail", ""))
        for item in data.get("action_ideas", [])
        if isinstance(item, dict)
    ]
    return Theme(
        theme_name=str(data.get("theme_name", "Untitled theme")),
        summary=str(data.get("summary", "")),
        quotes=[str(q) for q in data.get("quotes", [])],
        action_ideas=action_ideas,
        cluster_size=cluster.size,
        average_rating=cluster.avg_rating,
    )


def summarize_clusters(
    clusters: List[RankedCluster],
    config: SummarizationConfig,
    *,
    groq_client: Optional[GroqClient] = None,
    max_tokens_per_run: Optional[int] = None,
) -> tuple[List[Theme], GroqUsageStats]:
    """Summarize ranked clusters sequentially with rate limiting and token budget."""
    if groq_client is None:
        groq_client = _default_groq_client(config)

    budget = max_tokens_per_run or config.max_tokens_per_run
    stats = GroqUsageStats()
    themes: List[Theme] = []

    for cluster in clusters:
        if stats.total_tokens >= budget:
            logger.warning("Groq token budget exhausted after %d themes", len(themes))
            break

        samples = _fit_samples_to_budget(
            cluster.samples,
            config.max_output_tokens_per_theme,
        )
        prompt = THEME_PROMPT.format(reviews=_format_reviews(samples))
        estimated_in = _estimate_tokens(prompt)
        if stats.total_tokens + estimated_in + config.max_output_tokens_per_theme > budget:
            logger.warning("Skipping cluster %s — would exceed token budget", cluster.label)
            continue

        theme = _summarize_with_retry(
            cluster,
            prompt,
            config,
            groq_client,
            stats,
            source_texts=[s.text for s in samples],
        )
        if theme:
            themes.append(theme)

        if config.request_interval_seconds > 0:
            time.sleep(config.request_interval_seconds)

    return themes, stats


def _summarize_with_retry(
    cluster: RankedCluster,
    prompt: str,
    config: SummarizationConfig,
    groq_client: GroqClient,
    stats: GroqUsageStats,
    *,
    source_texts: Optional[List[str]] = None,
    max_attempts: int = 2,
) -> Optional[Theme]:
    source_texts = source_texts or [s.text for s in cluster.samples]
    current_prompt = prompt
    last_theme: Optional[Theme] = None

    for attempt in range(max_attempts):
        raw, tokens_in, tokens_out = groq_client.complete(
            current_prompt,
            config.max_output_tokens_per_theme,
        )
        stats.requests += 1
        stats.tokens_in += tokens_in
        stats.tokens_out += tokens_out

        try:
            theme = _parse_theme_response(raw, cluster)
        except SummarizationError:
            logger.warning("Failed to parse Groq response for cluster %s", cluster.label)
            return None

        last_theme = theme
        valid, invalid = validate_quotes(theme.quotes, source_texts)
        if not invalid:
            theme.quotes = valid
            return theme

        stats.re_prompts += 1
        logger.info(
            "Re-prompting cluster %s: %d invalid quotes",
            cluster.label,
            len(invalid),
        )
        current_prompt = (
            prompt
            + "\n\nIMPORTANT: These quotes were NOT found verbatim in the reviews: "
            + json.dumps(invalid)
            + "\nReturn corrected quotes that are exact substrings."
        )

    if last_theme:
        valid, _ = validate_quotes(last_theme.quotes, source_texts)
        last_theme.quotes = valid
        return last_theme if valid else None
    return None


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


PER_REQUEST_TOKEN_CEILING = 10_000


def _fit_samples_to_budget(
    samples: List[Review],
    max_output_tokens: int,
) -> List[Review]:
    """Drop longest samples until prompt estimate is under per-request ceiling."""
    if not samples:
        return samples
    working = list(samples)
    while working:
        prompt = THEME_PROMPT.format(reviews=_format_reviews(working))
        if _estimate_tokens(prompt) + max_output_tokens <= PER_REQUEST_TOKEN_CEILING:
            return working
        longest = max(range(len(working)), key=lambda i: len(working[i].text))
        working.pop(longest)
    return samples[:1]


class _GroqSdkClient:
    def __init__(self, model: str) -> None:
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise SummarizationError("GROQ_API_KEY is required for summarization")
        from groq import Groq

        self._client = Groq(api_key=api_key)
        self._model = model

    def complete(self, prompt: str, max_output_tokens: int) -> tuple[str, int, int]:
        last_error: Optional[Exception] = None
        for attempt in range(3):
            try:
                response = self._client.chat.completions.create(
                    model=self._model,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=max_output_tokens,
                    response_format={"type": "json_object"},
                    temperature=0.2,
                )
                text = response.choices[0].message.content or ""
                usage = response.usage
                tokens_in = usage.prompt_tokens if usage else _estimate_tokens(prompt)
                tokens_out = usage.completion_tokens if usage else _estimate_tokens(text)
                return text, tokens_in, tokens_out
            except Exception as exc:
                last_error = exc
                status = getattr(exc, "status_code", None)
                if status not in (429, 529) and "429" not in str(exc) and "529" not in str(exc):
                    raise
                time.sleep(2**attempt)
        raise SummarizationError(f"Groq rate limit retries exhausted: {last_error}")


def _default_groq_client(config: SummarizationConfig) -> GroqClient:
    return _GroqSdkClient(config.model)
