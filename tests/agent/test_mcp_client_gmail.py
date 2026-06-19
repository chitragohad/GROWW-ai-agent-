"""Gmail MCP HTTP client tests."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from pulse.agent.mcp_client import GoogleMcpClient


def test_create_email_draft_sends_payload() -> None:
    client = GoogleMcpClient("https://example.test", approval_key="secret")
    payload = json.dumps(
        {
            "status": "success",
            "result": {"draft_id": "d-1", "message_id": "m-1"},
        }
    ).encode()

    with patch("urllib.request.urlopen") as mock_open:
        mock_response = MagicMock()
        mock_response.read.return_value = payload
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_open.return_value = mock_response

        result = client.create_email_draft(
            to="user@example.com",
            subject="Groww Weekly Review Pulse — 2026-W24",
            body="Plain text body",
        )

    assert result["status"] == "success"
    request = mock_open.call_args[0][0]
    sent = json.loads(request.data.decode())
    assert sent["to"] == "user@example.com"
    assert sent["subject"].startswith("Groww")
