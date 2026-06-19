"""Assemble render outputs and optional preview artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from pulse.ingestion.models import PulseReport
from pulse.render.doc_section import render_doc_section
from pulse.render.email_teaser import render_email_teaser
from pulse.render.models import DocSection, EmailTeaser


class RenderedOutput:
    def __init__(self, doc_section: DocSection, email_teaser: EmailTeaser) -> None:
        self.doc_section = doc_section
        self.email_teaser = email_teaser


def render_report(
    report: PulseReport,
    *,
    deep_link: Optional[str] = None,
    doc_url: Optional[str] = None,
) -> RenderedOutput:
    return RenderedOutput(
        doc_section=render_doc_section(report),
        email_teaser=render_email_teaser(report, deep_link=deep_link, doc_url=doc_url),
    )


def write_preview_artifacts(
    rendered: RenderedOutput,
    run_dir: Path,
) -> dict[str, Path]:
    """Write render previews to a run directory (for local dev only)."""
    run_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "doc_section": run_dir / "doc_section.json",
        "doc_section_txt": run_dir / "doc_section.txt",
        "email_teaser": run_dir / "email_teaser.json",
        "email_html": run_dir / "email.html",
        "email_text": run_dir / "email.txt",
    }
    with paths["doc_section"].open("w", encoding="utf-8") as handle:
        json.dump(rendered.doc_section.model_dump(mode="json"), handle, indent=2, ensure_ascii=False)
    paths["doc_section_txt"].write_text(rendered.doc_section.content, encoding="utf-8")
    with paths["email_teaser"].open("w", encoding="utf-8") as handle:
        json.dump(rendered.email_teaser.model_dump(mode="json"), handle, indent=2, ensure_ascii=False)
    paths["email_html"].write_text(rendered.email_teaser.html_body, encoding="utf-8")
    paths["email_text"].write_text(rendered.email_teaser.text_body, encoding="utf-8")
    return paths
