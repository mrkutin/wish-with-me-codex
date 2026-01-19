from __future__ import annotations

import json
import logging
import os
from io import StringIO
from unittest.mock import patch

import pytest

from app.logging_config import JSONFormatter, configure_logging
from app.middleware import request_id_var


class TestJSONFormatter:
    def test_formats_basic_log_as_json(self) -> None:
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        output = formatter.format(record)
        parsed = json.loads(output)

        assert parsed["level"] == "INFO"
        assert parsed["logger"] == "test.logger"
        assert parsed["message"] == "Test message"
        assert "timestamp" in parsed

    def test_includes_trace_id_when_set(self) -> None:
        formatter = JSONFormatter()
        token = request_id_var.set("test-trace-id-123")
        try:
            record = logging.LogRecord(
                name="test",
                level=logging.INFO,
                pathname="test.py",
                lineno=1,
                msg="With trace",
                args=(),
                exc_info=None,
            )
            output = formatter.format(record)
            parsed = json.loads(output)
            assert parsed.get("trace_id") == "test-trace-id-123"
        finally:
            request_id_var.reset(token)

    def test_excludes_trace_id_when_not_set(self) -> None:
        formatter = JSONFormatter()
        token = request_id_var.set(None)
        try:
            record = logging.LogRecord(
                name="test",
                level=logging.INFO,
                pathname="test.py",
                lineno=1,
                msg="No trace",
                args=(),
                exc_info=None,
            )
            output = formatter.format(record)
            parsed = json.loads(output)
            assert "trace_id" not in parsed
        finally:
            request_id_var.reset(token)

    def test_includes_exception_info(self) -> None:
        formatter = JSONFormatter()
        try:
            raise ValueError("Test error")
        except ValueError:
            import sys

            exc_info = sys.exc_info()

        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="test.py",
            lineno=1,
            msg="Error occurred",
            args=(),
            exc_info=exc_info,
        )
        output = formatter.format(record)
        parsed = json.loads(output)

        assert "exception" in parsed
        assert "ValueError" in parsed["exception"]
        assert "Test error" in parsed["exception"]

    def test_handles_message_with_args(self) -> None:
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Value is %s and count is %d",
            args=("foo", 42),
            exc_info=None,
        )
        output = formatter.format(record)
        parsed = json.loads(output)
        assert parsed["message"] == "Value is foo and count is 42"


class TestConfigureLogging:
    def test_configures_json_format_by_default(self) -> None:
        os.environ.pop("LOG_FORMAT", None)
        os.environ["LOG_LEVEL"] = "INFO"

        # Clear existing handlers
        root = logging.getLogger()
        for h in root.handlers[:]:
            root.removeHandler(h)

        configure_logging()

        assert len(root.handlers) == 1
        handler = root.handlers[0]
        assert isinstance(handler.formatter, JSONFormatter)

    def test_configures_text_format_when_specified(self) -> None:
        os.environ["LOG_FORMAT"] = "text"
        os.environ["LOG_LEVEL"] = "INFO"

        root = logging.getLogger()
        for h in root.handlers[:]:
            root.removeHandler(h)

        configure_logging()

        assert len(root.handlers) == 1
        handler = root.handlers[0]
        assert not isinstance(handler.formatter, JSONFormatter)

    def test_respects_log_level(self) -> None:
        os.environ["LOG_FORMAT"] = "json"
        os.environ["LOG_LEVEL"] = "WARNING"

        root = logging.getLogger()
        for h in root.handlers[:]:
            root.removeHandler(h)

        configure_logging()

        assert root.level == logging.WARNING
