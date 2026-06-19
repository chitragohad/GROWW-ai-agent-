"""CLI ingest command tests."""

import json
from datetime import datetime, timezone

from pulse.cli import main
from pulse.ingestion.cache import CacheManifest
from pulse.ingestion.service import IngestionResult


def test_cli_ingest_command(monkeypatch, capsys):
    now = datetime.now(timezone.utc)
    manifest = CacheManifest(
        status="success",
        product="groww",
        package_id="com.nextbillion.groww",
        cache_date=now.date().isoformat(),
        window_weeks=10,
        window_start=now,
        window_end=now,
        raw_count=500,
        normalized_count=872,
        filter_stats={"normalized_count": 872},
    )
    fake_result = IngestionResult(
        product="groww",
        raw_reviews=[],
        normalized_reviews=[],
        manifest=manifest,
    )
    monkeypatch.setattr("pulse.cli.run_ingestion", lambda *args, **kwargs: fake_result)

    exit_code = main(["ingest", "--product", "groww", "--weeks-back", "10"])
    assert exit_code == 0

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["command"] == "ingest"
    assert payload["status"] == "success"
    assert payload["normalized_count"] == 872
