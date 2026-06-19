"""Email delivery and idempotency tests."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from pulse.agent.email_delivery import check_idempotency, create_email_draft, deliver_email_teaser
from pulse.agent.email_idempotency_store import EmailIdempotencyStore
from pulse.agent.mcp_client import McpClientError
from pulse.render.models import EmailTeaser


@pytest.fixture
def teaser() -> EmailTeaser:
    return EmailTeaser(
        subject="Groww Weekly Review Pulse — 2026-W23",
        html_body="<p>html</p>",
        text_body="Groww Weekly Review Pulse\n\nRead full report: https://docs.google.com/document/d/abc/edit",
        idempotency_key="groww-2026-W23-email",
        deep_link="https://docs.google.com/document/d/abc/edit",
    )


def test_check_idempotency_not_found(tmp_path, teaser: EmailTeaser) -> None:
    store = EmailIdempotencyStore(tmp_path / "email.json")
    result = check_idempotency(teaser.idempotency_key, store=store)
    assert result.already_sent is False


def test_create_email_draft_skips_duplicate(tmp_path, teaser: EmailTeaser) -> None:
    store = EmailIdempotencyStore(tmp_path / "email.json")
    store.record(teaser.idempotency_key, draft_id="d-1", message_id="m-1")
    client = MagicMock()

    result = create_email_draft(
        teaser,
        ["user@example.com"],
        client=client,
        store=store,
    )

    assert result.skipped_duplicate is True
    assert result.draft_created is False
    client.create_email_draft.assert_not_called()


def test_create_email_draft_calls_mcp(tmp_path, teaser: EmailTeaser) -> None:
    store = EmailIdempotencyStore(tmp_path / "email.json")
    client = MagicMock()
    client.create_email_draft.return_value = {
        "status": "success",
        "result": {"draft_id": "d-99", "message_id": "m-99"},
    }

    result = create_email_draft(
        teaser,
        ["a@example.com", "b@example.com"],
        client=client,
        store=store,
    )

    assert result.draft_created is True
    client.create_email_draft.assert_called_once_with(
        to="a@example.com, b@example.com",
        subject=teaser.subject,
        body=teaser.text_body,
    )

    second = create_email_draft(teaser, ["a@example.com"], client=client, store=store)
    assert second.skipped_duplicate is True


def test_deliver_email_teaser_rejects_send_mode(tmp_path, teaser: EmailTeaser) -> None:
    client = MagicMock()
    with pytest.raises(McpClientError, match="create_email_draft only"):
        deliver_email_teaser(
            teaser,
            ["user@example.com"],
            client=client,
            data_dir=tmp_path,
            mode="send",
        )
