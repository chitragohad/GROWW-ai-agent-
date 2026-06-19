"""Load render artifacts from a prior analysis run."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from pulse.agent.anchor_store import AnchorStore, default_anchor_store_path
from pulse.ingestion.models import PulseReport
from pulse.render.email_teaser import render_email_teaser
from pulse.render.models import DocSection, EmailTeaser
from pulse.render.preview import render_report


def load_report_from_run(run_dir: Path) -> PulseReport:
    path = run_dir / "report.json"
    if not path.is_file():
        raise FileNotFoundError(f"No report.json in {run_dir}")
    data = json.loads(path.read_text(encoding="utf-8"))
    return PulseReport.model_validate(data["report"])


def load_or_render_doc_section(run_dir: Path) -> DocSection:
    section_path = run_dir / "doc_section.json"
    if section_path.is_file():
        return DocSection.model_validate(json.loads(section_path.read_text(encoding="utf-8")))
    report = load_report_from_run(run_dir)
    return render_report(report).doc_section


def load_or_render_email_teaser(
    run_dir: Path,
    *,
    doc_url: Optional[str] = None,
) -> EmailTeaser:
    """Load teaser from disk or re-render from report (with optional Doc deep link)."""
    report_path = run_dir / "report.json"
    if report_path.is_file():
        report = load_report_from_run(run_dir)
        return render_email_teaser(report, doc_url=doc_url, deep_link=doc_url)

    teaser_path = run_dir / "email_teaser.json"
    if teaser_path.is_file():
        teaser = EmailTeaser.model_validate(json.loads(teaser_path.read_text(encoding="utf-8")))
        if doc_url and not teaser.deep_link:
            return teaser.model_copy(update={"deep_link": doc_url})
        return teaser

    raise FileNotFoundError(f"No report.json or email_teaser.json in {run_dir}")


def doc_url_for_anchor(data_dir: Path, anchor: str) -> Optional[str]:
    """Resolve Doc URL from Phase 5 anchor ledger."""
    record = AnchorStore(default_anchor_store_path(data_dir)).get_record(anchor)
    if not record:
        return None
    return record.get("url")
