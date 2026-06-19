"""Local anchor ledger for Doc append idempotency (server has no lookup API)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from pulse.agent.models import AnchorLookupResult


class AnchorStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def lookup(self, anchor: str, document_id: str) -> AnchorLookupResult:
        record = self.get_record(anchor)
        if not record or record.get("document_id") != document_id:
            return AnchorLookupResult(found=False, anchor=anchor)
        return AnchorLookupResult(
            found=True,
            anchor=anchor,
            document_id=document_id,
            url=record.get("url"),
            appended_at=_parse_dt(record.get("appended_at")),
        )

    def get_record(self, anchor: str) -> Optional[dict]:
        return self._all().get(anchor)

    def record(self, anchor: str, document_id: str, url: str) -> None:
        data = self._all()
        data[anchor] = {
            "document_id": document_id,
            "url": url,
            "appended_at": datetime.now(timezone.utc).isoformat(),
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


def default_anchor_store_path(data_dir: Path) -> Path:
    return data_dir / "deliveries" / "doc_anchors.json"


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))
