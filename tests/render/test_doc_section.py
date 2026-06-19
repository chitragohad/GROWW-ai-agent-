"""Doc section rendering tests."""

from __future__ import annotations

from pulse.ingestion.models import PulseReport
from pulse.render.doc_section import render_doc_section
from tests.render.conftest import load_golden, load_golden_json


def test_doc_section_matches_golden_json(sample_report: PulseReport, golden_dir) -> None:
    section = render_doc_section(sample_report)
    expected = load_golden_json("doc_section.json", golden_dir)
    assert section.model_dump(mode="json") == expected


def test_doc_section_matches_golden_text(sample_report: PulseReport, golden_dir) -> None:
    section = render_doc_section(sample_report)
    assert section.content == load_golden("doc_section.txt", golden_dir)


def test_doc_section_structure(sample_report: PulseReport) -> None:
    section = render_doc_section(sample_report)
    assert section.anchor == "groww-2026-W23"
    assert section.heading_text in section.content
    assert "Top themes" in section.content
    assert "Real user quotes" in section.content
    assert "Who this helps" in section.content


def test_doc_section_omits_action_ideas_when_empty(sample_report: PulseReport) -> None:
    for theme in sample_report.themes:
        theme.action_ideas = []
    section = render_doc_section(sample_report)
    assert "Action ideas" not in section.content
