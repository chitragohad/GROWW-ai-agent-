"""Local idempotency ledger for email drafts (server has no check API)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from pulse.agent.models import IdempotencyCheckResult


class EmailIdempotencyStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def check(self, idempotency_key: str) -> IdempotencyCheckResult:
        record = self._all().get(idempotency_key)
        if not record:
            return IdempotencyCheckResult(
                already_sent=False,
                idempotency_key=idempotency_key,
            )
        return IdempotencyCheckResult(
            already_sent=True,
            idempotency_key=idempotency_key,
            draft_id=record.get("draft_id"),
            message_id=record.get("message_id"),
            created_at=_parse_dt(record.get("created_at")),
        )

    def record(
        self,
        idempotency_key: str,
        *,
        draft_id: Optional[str] = None,
        message_id: Optional[str] = None,
        recipients: Optional[list[str]] = None,
        subject: Optional[str] = None,
    ) -> None:
        data = self._all()
        data[idempotency_key] = {
            "draft_id": draft_id,
            "message_id": message_id,
            "recipients": recipients or [],
            "subject": subject,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self._write(data)

    def _all(self) -> dict:
        if not self.path.is_file():
            return {}
        with self.path.open(encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}

    def _write(self, data: dict) -> None:
        with self.path.open("w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, ensure_ascii=False)


def default_email_idempotency_path(data_dir: Path) -> Path:
    return data_dir / "deliveries" / "email_idempotency.json"


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))
