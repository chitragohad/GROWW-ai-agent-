"""Run ledger data models (Phase 7)."""

from __future__ import annotations

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel


class DeliveryRecord(BaseModel):
    channel: Literal["google_doc", "gmail"]
    external_id: str
    url: Optional[str] = None
    idempotency_key: Optional[str] = None


class RunRecord(BaseModel):
    run_id: str
    product: str
    iso_week: str
    status: Literal["pending", "completed", "failed"]
    review_count: Optional[int] = None
    window_weeks: Optional[int] = None
    started_at: datetime
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    deliveries: List[DeliveryRecord] = []
