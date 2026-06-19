"""deliver-email CLI tests."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from pulse.agent.models import EmailDeliveryResult
from pulse.cli import main


def test_deliver_email_cli_dry_run(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "report.json").write_text(
        """
{
  "report": {
    "product": "groww",
    "display_name": "Groww",
    "iso_week": "2026-W23",
    "window_weeks": 10,
    "review_count": 100,
    "source": "google_play",
    "generated_at": "2026-06-08T10:30:00Z",
    "themes": [
      {
        "theme_name": "Test",
        "summary": "Summary text",
        "quotes": ["quote one"],
        "action_ideas": []
      }
    ]
  }
}
""".strip(),
        encoding="utf-8",
    )

    with patch("pulse.cli.GoogleMcpClient") as mock_client_cls:
        mock_client_cls.return_value = MagicMock()
        with patch("pulse.cli.deliver_email_teaser") as mock_deliver:
            mock_deliver.return_value = EmailDeliveryResult(
                idempotency_key="groww-2026-W23-email",
                subject="Groww Weekly Review Pulse — 2026-W23",
                recipients=["user@example.com"],
                draft_created=False,
                skipped_duplicate=False,
                doc_url="https://docs.google.com/document/d/abc/edit",
                mode="draft",
            )
            exit_code = main(
                [
                    "deliver-email",
                    "--product",
                    "groww",
                    "--run-dir",
                    str(run_dir),
                    "--to",
                    "user@example.com",
                    "--dry-run",
                ]
            )

    assert exit_code == 0
    mock_deliver.assert_called_once()
