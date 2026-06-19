"""Run failure and partial-delivery alerting (Phase 9)."""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Literal, Optional

from pulse.ledger.models import RunRecord
from pulse.logging import log_event

logger = logging.getLogger(__name__)


@dataclass
class RunAlert:
    severity: Literal["failed", "partial"]
    product: str
    iso_week: str
    run_id: str
    message: str
    error_message: Optional[str] = None


def classify_run_record(record: RunRecord) -> Optional[RunAlert]:
    """Return an alert when a run failed or partially delivered."""
    if record.status != "failed":
        return None

    channels = {delivery.channel for delivery in record.deliveries}
    if "google_doc" in channels and "gmail" not in channels:
        return RunAlert(
            severity="partial",
            product=record.product,
            iso_week=record.iso_week,
            run_id=record.run_id,
            message="Doc delivered but Gmail failed — retry will skip Doc append",
            error_message=record.error_message,
        )

    return RunAlert(
        severity="failed",
        product=record.product,
        iso_week=record.iso_week,
        run_id=record.run_id,
        message=record.error_message or "Pulse run failed",
        error_message=record.error_message,
    )


def emit_run_alert(
    alert: RunAlert,
    *,
    webhook_url: Optional[str] = None,
) -> None:
    """Log structured alert and optionally POST to a webhook (Slack-compatible)."""
    log_event(
        logger,
        f"pulse alert: {alert.severity}",
        level=logging.ERROR,
        run_id=alert.run_id,
        product=alert.product,
        iso_week=alert.iso_week,
        stage="monitoring",
        context={
            "severity": alert.severity,
            "message": alert.message,
            "error_message": alert.error_message,
        },
    )

    if not webhook_url:
        return

    payload = {
        "text": (
            f"*[pulse {alert.severity}]* {alert.product} {alert.iso_week}\n"
            f"run_id: {alert.run_id}\n"
            f"{alert.message}"
        ),
        "severity": alert.severity,
        "product": alert.product,
        "iso_week": alert.iso_week,
        "run_id": alert.run_id,
        "error_message": alert.error_message,
    }
    _post_webhook(webhook_url, payload)


def _post_webhook(url: str, payload: dict) -> None:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            if response.status >= 400:
                log_event(
                    logger,
                    "alert webhook returned error status",
                    level=logging.WARNING,
                    stage="monitoring",
                    context={"status": response.status},
                )
    except urllib.error.URLError as exc:
        log_event(
            logger,
            "alert webhook request failed",
            level=logging.WARNING,
            stage="monitoring",
            context={"error": str(exc)},
        )
