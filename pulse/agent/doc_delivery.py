"""Google Doc delivery via hosted MCP (Phase 5)."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from pulse.agent.anchor_store import AnchorStore, default_anchor_store_path
from pulse.agent.mcp_client import GoogleMcpClient
from pulse.agent.models import AnchorLookupResult, AppendSectionResult, DocDeliveryResult
from pulse.render.models import DocSection


def get_document_url(document_id: str) -> str:
    return f"https://docs.google.com/document/d/{document_id}/edit"


def find_section_by_anchor(
    anchor: str,
    document_id: str,
    *,
    store: AnchorStore,
) -> AnchorLookupResult:
    """Client-side idempotency lookup (Chitra MCP has no server-side anchor API)."""
    return store.lookup(anchor, document_id)


def append_section(
    doc_section: DocSection,
    document_id: str,
    *,
    client: GoogleMcpClient,
    store: AnchorStore,
    dry_run: bool = False,
) -> AppendSectionResult:
    """Append plain-text section if anchor not already recorded for this document."""
    url = get_document_url(document_id)
    existing = find_section_by_anchor(doc_section.anchor, document_id, store=store)
    if existing.found:
        return AppendSectionResult(
            anchor=doc_section.anchor,
            document_id=document_id,
            url=existing.url or url,
            appended=False,
            skipped_duplicate=True,
        )

    content = doc_section.content
    if not content.startswith("\n"):
        content = f"\n{content}"

    if dry_run:
        return AppendSectionResult(
            anchor=doc_section.anchor,
            document_id=document_id,
            url=url,
            appended=False,
            skipped_duplicate=False,
            server_response={"status": "dry_run"},
        )

    response = client.append_to_doc(document_id, content)
    store.record(doc_section.anchor, document_id, url)
    return AppendSectionResult(
        anchor=doc_section.anchor,
        document_id=document_id,
        url=url,
        appended=True,
        skipped_duplicate=False,
        server_response=response,
    )


def deliver_doc_section(
    doc_section: DocSection,
    document_id: str,
    *,
    client: GoogleMcpClient,
    data_dir: Path,
    dry_run: bool = False,
    store: Optional[AnchorStore] = None,
) -> DocDeliveryResult:
    store = store or AnchorStore(default_anchor_store_path(data_dir))
    result = append_section(
        doc_section,
        document_id,
        client=client,
        store=store,
        dry_run=dry_run,
    )
    return DocDeliveryResult(
        anchor=result.anchor,
        document_id=result.document_id,
        url=result.url,
        appended=result.appended,
        skipped_duplicate=result.skipped_duplicate,
    )
