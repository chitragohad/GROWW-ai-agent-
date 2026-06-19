"""Structured logging tests."""

import json
import logging

from pulse.logging import JsonFormatter, log_event


def test_json_formatter_outputs_parseable_json():
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="pulse.test",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="hello",
        args=(),
        exc_info=None,
    )
    record.product = "groww"
    record.iso_week = "2026-W23"
    record.stage = "test"
    record.context = {"key": "value"}

    line = formatter.format(record)
    payload = json.loads(line)
    assert payload["message"] == "hello"
    assert payload["product"] == "groww"
    assert payload["iso_week"] == "2026-W23"


def test_setup_logging_and_log_event(capsys):
    # Use a dedicated logger to avoid cross-test handler state on the pulse root logger.
    test_logger = logging.getLogger("pulse.test.logging")
    test_logger.handlers.clear()
    test_logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    test_logger.addHandler(handler)
    test_logger.propagate = False

    log_event(test_logger, "test event", product="groww", stage="test")
    captured = capsys.readouterr()
    assert '"message": "test event"' in captured.err
