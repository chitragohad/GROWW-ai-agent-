"""Structured JSON logging for pulse pipeline stages."""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any, Dict, Optional


class JsonFormatter(logging.Formatter):
    """Emit one JSON object per log line."""

    def format(self, record: logging.LogRecord) -> str:
        payload: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key in ("run_id", "product", "iso_week", "stage", "context"):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def setup_logging(*, level: int = logging.INFO) -> logging.Logger:
    """Configure root logger with JSON output to stdout."""
    root = logging.getLogger("pulse")
    if root.handlers:
        return root

    root.setLevel(level)
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)
    root.propagate = False
    return root


def get_logger(name: Optional[str] = None) -> logging.Logger:
    return logging.getLogger(name or "pulse")


def log_event(
    logger: logging.Logger,
    message: str,
    *,
    level: int = logging.INFO,
    run_id: Optional[str] = None,
    product: Optional[str] = None,
    iso_week: Optional[str] = None,
    stage: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
) -> None:
    """Log a structured event with optional run context fields."""
    record_extra: Dict[str, Any] = {"context": context or {}}
    if run_id is not None:
        record_extra["run_id"] = run_id
    if product is not None:
        record_extra["product"] = product
    if iso_week is not None:
        record_extra["iso_week"] = iso_week
    if stage is not None:
        record_extra["stage"] = stage
    logger.log(level, message, extra=record_extra)
