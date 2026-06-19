"""Delivery result models for Google MCP integration."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class AnchorLookupResult(BaseModel):
    found: bool
    anchor: str
    document_id: Optional[str] = None
    url: Optional[str] = None
    appended_at: Optional[datetime] = None


class AppendSectionResult(BaseModel):
    anchor: str
    document_id: str
    url: str
    appended: bool
    skipped_duplicate: bool = False
    server_response: Optional[dict] = None


class DocDeliveryResult(BaseModel):
    anchor: str
    document_id: str
    url: str
    appended: bool
    skipped_duplicate: bool


class IdempotencyCheckResult(BaseModel):
    already_sent: bool
    idempotency_key: str
    draft_id: Optional[str] = None
    message_id: Optional[str] = None
    created_at: Optional[datetime] = None


class EmailDeliveryResult(BaseModel):
    idempotency_key: str
    subject: str
    recipients: list[str]
    draft_created: bool
    skipped_duplicate: bool
    draft_id: Optional[str] = None
    message_id: Optional[str] = None
    doc_url: Optional[str] = None
    mode: str = "draft"
