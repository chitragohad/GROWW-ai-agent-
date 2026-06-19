"""Render PulseReport into a short stakeholder email teaser."""

from __future__ import annotations

import html
from typing import List, Optional

from pulse.ingestion.models import PulseReport, Theme
from pulse.render.anchors import email_idempotency_key, email_subject
from pulse.render.doc_section import _format_generated_at
from pulse.render.models import EmailTeaser

MAX_THEME_NAME_EMAIL = 60
MAX_THEME_SUMMARY_EMAIL = 120
CTA_PLACEHOLDER = "https://docs.google.com/document/d/PLACEHOLDER#heading=PLACEHOLDER"


def render_email_teaser(
    report: PulseReport,
    *,
    deep_link: Optional[str] = None,
    doc_url: Optional[str] = None,
) -> EmailTeaser:
    """Pure function: PulseReport → email subject + HTML/text bodies."""
    subject = email_subject(report.display_name, report.iso_week)
    idempotency_key = email_idempotency_key(report.product, report.iso_week)
    link = deep_link or doc_url or CTA_PLACEHOLDER

    theme_lines = _email_theme_lines(report.themes)
    generated = _format_generated_at(report.generated_at)
    footer_doc_url = doc_url or link

    text_body = _render_text_body(
        report=report,
        theme_lines=theme_lines,
        link=link,
        footer_doc_url=footer_doc_url,
        generated=generated,
    )
    html_body = _render_html_body(
        report=report,
        theme_lines=theme_lines,
        link=link,
        footer_doc_url=footer_doc_url,
        generated=generated,
    )

    return EmailTeaser(
        subject=subject,
        html_body=html_body,
        text_body=text_body,
        idempotency_key=idempotency_key,
        deep_link=link if link != CTA_PLACEHOLDER else None,
    )


def _email_theme_lines(themes: List[Theme]) -> List[str]:
    lines: List[str] = []
    for theme in themes[:5]:
        name = _truncate(theme.theme_name, MAX_THEME_NAME_EMAIL)
        summary = _truncate(theme.summary, MAX_THEME_SUMMARY_EMAIL)
        lines.append(f"{name} — {summary}")
    return lines


def _truncate(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - 3].rstrip() + "..."


def _render_text_body(
    *,
    report: PulseReport,
    theme_lines: List[str],
    link: str,
    footer_doc_url: str,
    generated: str,
) -> str:
    bullets = "\n".join(f"• {line}" for line in theme_lines)
    return (
        f"{report.display_name} Weekly Review Pulse — {report.iso_week}\n\n"
        f"Top themes from the last {report.window_weeks} weeks of Play Store reviews:\n\n"
        f"{bullets}\n\n"
        f"Read full report: {link}\n\n"
        f"---\n"
        f"Generated: {generated}\n"
        f"Review window: last {report.window_weeks} weeks · {report.review_count} reviews analyzed\n"
        f"Full document: {footer_doc_url}"
    )


def _render_html_body(
    *,
    report: PulseReport,
    theme_lines: List[str],
    link: str,
    footer_doc_url: str,
    generated: str,
) -> str:
    items = "".join(f"<li>{html.escape(line)}</li>" for line in theme_lines)
    return (
        "<html><body>"
        f"<p><strong>{html.escape(report.display_name)} Weekly Review Pulse — "
        f"{html.escape(report.iso_week)}</strong></p>"
        f"<p>Top themes from the last {report.window_weeks} weeks of Play Store reviews:</p>"
        f"<ul>{items}</ul>"
        f'<p><a href="{html.escape(link, quote=True)}">Read full report</a></p>'
        "<hr>"
        f"<p><small>Generated: {html.escape(generated)}<br>"
        f"Review window: last {report.window_weeks} weeks · "
        f"{report.review_count} reviews analyzed<br>"
        f'Full document: <a href="{html.escape(footer_doc_url, quote=True)}">'
        f"{html.escape(footer_doc_url)}</a></small></p>"
        "</body></html>"
    )
