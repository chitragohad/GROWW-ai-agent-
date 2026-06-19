"""deliver-doc CLI tests."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from pulse.agent.models import DocDeliveryResult
from pulse.cli import main
from pulse.render.models import DocSection


def test_deliver_doc_cli_dry_run(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "doc_section.json").write_text(
        DocSection(
            anchor="groww-2026-W23",
            heading_text="Groww — Weekly Review Pulse — 2026-W23",
            content="test content",
        ).model_dump_json(),
        encoding="utf-8",
    )

    with patch("pulse.cli.GoogleMcpClient") as mock_client_cls:
        mock_client_cls.return_value = MagicMock()
        with patch("pulse.cli.deliver_doc_section") as mock_deliver:
            mock_deliver.return_value = DocDeliveryResult(
                anchor="groww-2026-W23",
                document_id="doc-123",
                url="https://docs.google.com/document/d/doc-123/edit",
                appended=False,
                skipped_duplicate=False,
            )
            exit_code = main(
                [
                    "deliver-doc",
                    "--product",
                    "groww",
                    "--run-dir",
                    str(run_dir),
                    "--doc-id",
                    "doc-123",
                    "--dry-run",
                ]
            )

    assert exit_code == 0
    mock_deliver.assert_called_once()
