"""Render preview artifact tests."""

from __future__ import annotations

from pulse.ingestion.models import PulseReport
from pulse.render.preview import render_report, write_preview_artifacts


def test_write_preview_artifacts(sample_report: PulseReport, tmp_path) -> None:
    rendered = render_report(sample_report)
    paths = write_preview_artifacts(rendered, tmp_path)

    assert paths["doc_section"].is_file()
    assert paths["doc_section_txt"].is_file()
    assert paths["email_teaser"].is_file()
    assert paths["email_html"].is_file()
    assert paths["email_text"].is_file()
    assert "Poor Support" in paths["doc_section_txt"].read_text(encoding="utf-8")
