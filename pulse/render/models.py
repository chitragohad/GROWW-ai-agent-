"""Output models for Doc sections and email teasers."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class DocSection(BaseModel):
    """Plain-text weekly section for append-only Docs MCP."""

    anchor: str
    heading_text: str
    content: str


class EmailTeaser(BaseModel):
    subject: str
    html_body: str
    text_body: str
    idempotency_key: str
    deep_link: Optional[str] = None
