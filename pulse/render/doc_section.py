"""Render PulseReport into plain-text Google Doc content."""

from __future__ import annotations

from datetime import datetime
from typing import List
from zoneinfo import ZoneInfo

from pulse.ingestion.models import PulseReport, Theme
from pulse.render.anchors import section_anchor, section_heading_text
from pulse.render.models import DocSection

WHO_THIS_HELPS = [
    "Product — Prioritize roadmap items backed by clustered Play Store feedback and validated user quotes.",
    "Support — Spot recurring complaint themes early and align macros or escalation paths.",
    "Leadership — Get a weekly, scannable snapshot of user sentiment without reading raw reviews.",
]

SOURCE_LABELS = {
    "google_play": "Google Play Store",
}


def render_doc_section(report: PulseReport) -> DocSection:
    """Pure function: PulseReport → plain text section for append-only Docs MCP."""
    anchor = section_anchor(report.product, report.iso_week)
    heading = section_heading_text(report.display_name, report.iso_week)
    lines: List[str] = [
        heading,
        f"Anchor: {anchor}",
        "",
        _period_line(report),
        "",
        "Top themes",
        *_bullet_lines(_theme_bullets(report.themes)),
        "",
        "Real user quotes",
        *_bullet_lines(_quote_bullets(report.themes)),
    ]

    action_items = _action_bullets(report.themes)
    if action_items:
        lines.extend(["", "Action ideas", *_bullet_lines(action_items)])

    lines.extend(
        [
            "",
            "Who this helps",
            *_bullet_lines(WHO_THIS_HELPS),
        ]
    )

    return DocSection(anchor=anchor, heading_text=heading, content="\n".join(lines))


def _bullet_lines(items: List[str]) -> List[str]:
    return [f"• {item}" for item in items]


def _period_line(report: PulseReport) -> str:
    generated = _format_generated_at(report.generated_at)
    source = SOURCE_LABELS.get(report.source, report.source)
    return (
        f"Period: Last {report.window_weeks} weeks (rolling) · "
        f"Source: {source} · "
        f"Reviews analyzed: {report.review_count} · "
        f"Generated: {generated}"
    )


def _format_generated_at(value: datetime) -> str:
    ist = value.astimezone(ZoneInfo("Asia/Kolkata"))
    return ist.strftime("%Y-%m-%d %H:%M IST")


def _theme_bullets(themes: List[Theme]) -> List[str]:
    return [f"{theme.theme_name} — {theme.summary}" for theme in themes]


def _quote_bullets(themes: List[Theme]) -> List[str]:
    quotes: List[str] = []
    for theme in themes:
        quotes.extend(theme.quotes)
    return quotes


def _action_bullets(themes: List[Theme]) -> List[str]:
    items: List[str] = []
    for theme in themes:
        for idea in theme.action_ideas:
            items.append(f"{idea.title} — {idea.detail}")
    return items
