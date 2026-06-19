"""Gmail draft delivery via hosted MCP (Phase 6)."""

from __future__ import annotations

from pathlib import Path
from typing import Literal, Optional

from pulse.agent.email_idempotency_store import EmailIdempotencyStore, default_email_idempotency_path
from pulse.agent.mcp_client import GoogleMcpClient, McpClientError
from pulse.agent.models import EmailDeliveryResult, IdempotencyCheckResult
from pulse.render.models import EmailTeaser


def check_idempotency(
    idempotency_key: str,
    *,
    store: EmailIdempotencyStore,
) -> IdempotencyCheckResult:
    """Client-side duplicate check (Chitra MCP has no idempotency API)."""
    return store.check(idempotency_key)


def create_email_draft(
    teaser: EmailTeaser,
    recipients: list[str],
    *,
    client: GoogleMcpClient,
    store: EmailIdempotencyStore,
    dry_run: bool = False,
) -> EmailDeliveryResult:
    """Create Gmail draft via MCP if idempotency key not already used."""
    if not recipients:
        raise ValueError("At least one recipient is required")

    existing = check_idempotency(teaser.idempotency_key, store=store)
    if existing.already_sent:
        return EmailDeliveryResult(
            idempotency_key=teaser.idempotency_key,
            subject=teaser.subject,
            recipients=recipients,
            draft_created=False,
            skipped_duplicate=True,
            draft_id=existing.draft_id,
            message_id=existing.message_id,
            doc_url=teaser.deep_link,
            mode="draft",
        )

    if dry_run:
        return EmailDeliveryResult(
            idempotency_key=teaser.idempotency_key,
            subject=teaser.subject,
            recipients=recipients,
            draft_created=False,
            skipped_duplicate=False,
            doc_url=teaser.deep_link,
            mode="draft",
        )

    to_header = ", ".join(recipients)
    response = client.create_email_draft(
        to=to_header,
        subject=teaser.subject,
        body=teaser.text_body,
    )
    result_payload = response.get("result", {})
    draft_id = result_payload.get("draft_id")
    message_id = result_payload.get("message_id")

    store.record(
        teaser.idempotency_key,
        draft_id=draft_id,
        message_id=message_id,
        recipients=recipients,
        subject=teaser.subject,
    )

    return EmailDeliveryResult(
        idempotency_key=teaser.idempotency_key,
        subject=teaser.subject,
        recipients=recipients,
        draft_created=True,
        skipped_duplicate=False,
        draft_id=draft_id,
        message_id=message_id,
        doc_url=teaser.deep_link,
        mode="draft",
    )


def deliver_email_teaser(
    teaser: EmailTeaser,
    recipients: list[str],
    *,
    client: GoogleMcpClient,
    data_dir: Path,
    mode: Literal["draft", "send"] = "draft",
    dry_run: bool = False,
    store: Optional[EmailIdempotencyStore] = None,
) -> EmailDeliveryResult:
    if mode == "send":
        raise McpClientError(
            "Hosted Chitra MCP server exposes create_email_draft only; "
            "use mode=draft or extend the MCP server with send_email."
        )

    store = store or EmailIdempotencyStore(default_email_idempotency_path(data_dir))
    return create_email_draft(
        teaser,
        recipients,
        client=client,
        store=store,
        dry_run=dry_run,
    )
