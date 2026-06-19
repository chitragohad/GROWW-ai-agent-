"""Pulse agent: MCP client and delivery orchestration."""

from pulse.agent.anchor_store import AnchorStore, default_anchor_store_path
from pulse.agent.doc_delivery import (
    append_section,
    deliver_doc_section,
    find_section_by_anchor,
    get_document_url,
)
from pulse.agent.email_delivery import check_idempotency, create_email_draft, deliver_email_teaser
from pulse.agent.mcp_client import DEFAULT_MCP_SERVER_URL, GoogleMcpClient, McpClientError
from pulse.agent.models import (
    AnchorLookupResult,
    AppendSectionResult,
    DocDeliveryResult,
    EmailDeliveryResult,
    IdempotencyCheckResult,
)

__all__ = [
    "AnchorLookupResult",
    "AppendSectionResult",
    "DEFAULT_MCP_SERVER_URL",
    "DocDeliveryResult",
    "EmailDeliveryResult",
    "GoogleMcpClient",
    "IdempotencyCheckResult",
    "McpClientError",
    "append_section",
    "check_idempotency",
    "create_email_draft",
    "deliver_doc_section",
    "deliver_email_teaser",
    "find_section_by_anchor",
    "get_document_url",
]
