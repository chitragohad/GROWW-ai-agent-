"""HTTP client for the hosted Chitra Google MCP server."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any, Optional

DEFAULT_MCP_SERVER_URL = "https://web-production-bf583.up.railway.app"
APPROVAL_HEADER = "X-Approval-Key"


class McpClientError(Exception):
    pass


class GoogleMcpClient:
    """
    Client for https://github.com/chitragohad/Chitra-MCP-server

    Endpoints:
      GET  /                  — health check
      POST /append_to_doc     — { doc_id, content }
      POST /create_email_draft — Phase 6
    """

    def __init__(
        self,
        base_url: str = DEFAULT_MCP_SERVER_URL,
        *,
        approval_key: Optional[str] = None,
        timeout_seconds: float = 60.0,
        max_retries: int = 3,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.approval_key = approval_key
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries

    def health_check(self) -> dict[str, Any]:
        return self._request("GET", "/")

    def append_to_doc(self, doc_id: str, content: str) -> dict[str, Any]:
        return self._request(
            "POST",
            "/append_to_doc",
            body={"doc_id": doc_id, "content": content},
        )

    def create_email_draft(self, to: str, subject: str, body: str) -> dict[str, Any]:
        return self._request(
            "POST",
            "/create_email_draft",
            body={"to": to, "subject": subject, "body": body},
        )

    def _request(
        self,
        method: str,
        path: str,
        *,
        body: Optional[dict] = None,
    ) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        headers = {"Accept": "application/json"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        if self.approval_key:
            headers[APPROVAL_HEADER] = self.approval_key

        data = json.dumps(body).encode("utf-8") if body is not None else None
        last_error: Optional[Exception] = None

        for attempt in range(self.max_retries):
            try:
                request = urllib.request.Request(url, data=data, headers=headers, method=method)
                with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                    raw = response.read().decode("utf-8")
                    return json.loads(raw) if raw else {}
            except urllib.error.HTTPError as exc:
                detail = _read_http_error(exc)
                if exc.code in (403, 401):
                    raise McpClientError(
                        f"MCP request rejected ({exc.code}): {detail}. "
                        "Set MCP_APPROVAL_KEY to match the server's APPROVAL_KEY."
                    ) from exc
                if exc.code >= 500 and attempt < self.max_retries - 1:
                    time.sleep(2**attempt)
                    last_error = exc
                    continue
                raise McpClientError(f"MCP HTTP {exc.code}: {detail}") from exc
            except urllib.error.URLError as exc:
                if attempt < self.max_retries - 1:
                    time.sleep(2**attempt)
                    last_error = exc
                    continue
                raise McpClientError(f"MCP connection failed: {exc.reason}") from exc

        raise McpClientError(f"MCP request failed after retries: {last_error}")


def _read_http_error(exc: urllib.error.HTTPError) -> str:
    try:
        payload = exc.read().decode("utf-8")
        parsed = json.loads(payload)
        if isinstance(parsed, dict) and "detail" in parsed:
            return str(parsed["detail"])
        return payload
    except Exception:
        return exc.reason or "unknown error"
