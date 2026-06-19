"""Doc delivery and anchor idempotency tests."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from pulse.agent.anchor_store import AnchorStore
from pulse.agent.doc_delivery import append_section, deliver_doc_section, find_section_by_anchor, get_document_url
from pulse.render.models import DocSection


@pytest.fixture
def doc_section() -> DocSection:
    return DocSection(
        anchor="groww-2026-W23",
        heading_text="Groww — Weekly Review Pulse — 2026-W23",
        content="Groww — Weekly Review Pulse — 2026-W23\nAnchor: groww-2026-W23\n\nTop themes\n• Test",
    )


def test_get_document_url() -> None:
    assert get_document_url("abc123") == "https://docs.google.com/document/d/abc123/edit"


def test_find_section_by_anchor_not_found(tmp_path, doc_section: DocSection) -> None:
    store = AnchorStore(tmp_path / "anchors.json")
    result = find_section_by_anchor(doc_section.anchor, "doc-1", store=store)
    assert result.found is False


def test_append_section_skips_duplicate(tmp_path, doc_section: DocSection) -> None:
    store = AnchorStore(tmp_path / "anchors.json")
    store.record(doc_section.anchor, "doc-1", get_document_url("doc-1"))
    client = MagicMock()

    result = append_section(doc_section, "doc-1", client=client, store=store)

    assert result.skipped_duplicate is True
    assert result.appended is False
    client.append_to_doc.assert_not_called()


def test_append_section_calls_mcp_client(tmp_path, doc_section: DocSection) -> None:
    store = AnchorStore(tmp_path / "anchors.json")
    client = MagicMock()
    client.append_to_doc.return_value = {"status": "success", "result": {"document_id": "doc-1"}}

    result = append_section(doc_section, "doc-1", client=client, store=store)

    assert result.appended is True
    client.append_to_doc.assert_called_once()
    args = client.append_to_doc.call_args[0]
    assert args[0] == "doc-1"
    assert doc_section.content in args[1]

    second = append_section(doc_section, "doc-1", client=client, store=store)
    assert second.skipped_duplicate is True
    assert client.append_to_doc.call_count == 1


def test_deliver_doc_section_dry_run(tmp_path, doc_section: DocSection) -> None:
    client = MagicMock()
    result = deliver_doc_section(
        doc_section,
        "doc-1",
        client=client,
        data_dir=tmp_path,
        dry_run=True,
    )
    assert result.appended is False
    client.append_to_doc.assert_not_called()
