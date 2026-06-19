"""Doc section and email teaser rendering (Phase 4)."""

from pulse.render.anchors import (
    email_idempotency_key,
    email_subject,
    section_anchor,
    section_heading_text,
    validate_iso_week,
)
from pulse.render.doc_section import render_doc_section
from pulse.render.email_teaser import render_email_teaser
from pulse.render.models import DocSection, EmailTeaser
from pulse.render.preview import RenderedOutput, render_report, write_preview_artifacts

__all__ = [
    "DocSection",
    "EmailTeaser",
    "RenderedOutput",
    "email_idempotency_key",
    "email_subject",
    "render_doc_section",
    "render_email_teaser",
    "render_report",
    "section_anchor",
    "section_heading_text",
    "validate_iso_week",
    "write_preview_artifacts",
]
