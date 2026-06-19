"""Google MCP HTTP client tests."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from pulse.agent.mcp_client import GoogleMcpClient, McpClientError


def test_health_check_parses_response() -> None:
    client = GoogleMcpClient("https://example.test")
    payload = json.dumps({"status": "ok", "message": "Google MCP Server is running"}).encode()

    with patch("urllib.request.urlopen") as mock_open:
        mock_response = MagicMock()
        mock_response.read.return_value = payload
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_open.return_value = mock_response

        result = client.health_check()

    assert result["status"] == "ok"


def test_append_to_doc_sends_approval_header() -> None:
    client = GoogleMcpClient("https://example.test", approval_key="secret-key")
    payload = json.dumps({"status": "success", "result": {"document_id": "abc"}}).encode()

    with patch("urllib.request.urlopen") as mock_open:
        mock_response = MagicMock()
        mock_response.read.return_value = payload
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_open.return_value = mock_response

        result = client.append_to_doc("abc", "\nHello")

    request = mock_open.call_args[0][0]
    assert request.get_header("X-approval-key") == "secret-key"
    assert result["status"] == "success"


def test_append_to_doc_raises_on_403() -> None:
    import urllib.error

    client = GoogleMcpClient("https://example.test", approval_key="wrong")

    with patch("urllib.request.urlopen") as mock_open:
        mock_open.side_effect = urllib.error.HTTPError(
            url="https://example.test/append_to_doc",
            code=403,
            msg="Forbidden",
            hdrs=None,
            fp=MagicMock(read=MagicMock(return_value=b'{"detail":"Action not approved"}')),
        )
        with pytest.raises(McpClientError, match="403"):
            client.append_to_doc("abc", "content")
