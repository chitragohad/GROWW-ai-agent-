"""Core data models for ingestion, runs, and reports."""

from __future__ import annotations

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class RawReview(BaseModel):
    """Full scrape payload for a single Play Store review."""

    text: str
    rating: int = Field(ge=1, le=5)
    published_at: datetime
    source: Literal["google_play"] = "google_play"
    package_id: Optional[str] = None
    review_id: Optional[str] = None


class Review(BaseModel):
    """Normalized review consumed by the analysis pipeline (text + rating only)."""

    text: str
    rating: int = Field(ge=1, le=5)


class RunContext(BaseModel):
    """Identifiers and parameters for a single pulse run."""

    run_id: str
    product: str
    iso_week: str
    window_weeks: int
    dry_run: bool = False
    email_mode: Literal["draft", "send"] = "draft"


class ActionIdea(BaseModel):
    title: str
    detail: str


class Theme(BaseModel):
    theme_name: str
    summary: str
    quotes: List[str] = Field(default_factory=list)
    action_ideas: List[ActionIdea] = Field(default_factory=list)
    cluster_size: Optional[int] = None
    average_rating: Optional[float] = None


class PulseReport(BaseModel):
    """Structured analysis output before rendering to Doc/email."""

    product: str
    display_name: str
    iso_week: str
    window_weeks: int
    review_count: int
    source: Literal["google_play"] = "google_play"
    generated_at: datetime
    themes: List[Theme] = Field(default_factory=list)
