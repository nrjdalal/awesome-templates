"""Tests for ``configure_logging`` + the stdlib → structlog bridge (#9)."""

from __future__ import annotations

import io
import json
import logging

import pytest
import structlog

from src._core.infrastructure.logging.configure import configure_logging


@pytest.fixture
def reset_structlog():
    """Reset structlog + root logger state between tests.

    structlog and the root logger both carry module-global state that
    persists across tests. Each test in this module reconfigures
    deliberately, so reset on teardown to avoid leaking the custom
    handler / renderer into unrelated tests.
    """
    yield
    structlog.reset_defaults()
    structlog.contextvars.clear_contextvars()
    logging.basicConfig(force=True)  # restore a plain root handler


def _capture_handler_output(logger_name: str, level: int = logging.INFO) -> io.StringIO:
    """Point the configured handler at an ``io.StringIO`` so tests can read it.

    ``configure_logging`` installs a ``StreamHandler`` pointing at
    ``sys.stdout``. Tests redirect it to a buffer by swapping the
    underlying stream — simpler than capturing OS file descriptors.
    """
    root = logging.getLogger(logger_name)
    for handler in root.handlers:
        if isinstance(handler, logging.StreamHandler):
            buffer = io.StringIO()
            handler.setStream(buffer)
            handler.setLevel(level)
            return buffer
    raise AssertionError("Expected a StreamHandler on the configured logger")


class TestConfigureLoggingJsonMode:
    def test_structlog_logger_emits_json(self, reset_structlog: None):
        configure_logging(log_level="INFO", json_logs=True)
        buffer = _capture_handler_output("")
        logger = structlog.stdlib.get_logger("test_json")

        logger.info("event_happened", key="value", count=3)

        output = buffer.getvalue()
        record = json.loads(output)
        assert record["event"] == "event_happened"
        assert record["key"] == "value"
        assert record["count"] == 3
        assert record["level"] == "info"
        assert record["logger"] == "test_json"
        assert "timestamp" in record

    def test_stdlib_logger_also_emits_json(self, reset_structlog: None):
        """`logging.getLogger()` routes through the same pipeline."""
        configure_logging(log_level="INFO", json_logs=True)
        buffer = _capture_handler_output("")
        logger = logging.getLogger("test_stdlib")

        logger.info("plain stdlib message")

        output = buffer.getvalue()
        record = json.loads(output)
        assert record["event"] == "plain stdlib message"
        assert record["logger"] == "test_stdlib"
        assert record["level"] == "info"


class TestConfigureLoggingConsoleMode:
    def test_console_mode_emits_plain_text(self, reset_structlog: None):
        configure_logging(log_level="INFO", json_logs=False)
        buffer = _capture_handler_output("")
        logger = structlog.stdlib.get_logger("test_console")

        logger.info("hello", name="alice")

        output = buffer.getvalue()
        # Console renderer produces human-readable text, not JSON.
        assert "hello" in output
        assert "alice" in output
        with pytest.raises(json.JSONDecodeError):
            json.loads(output)


class TestConfigureLoggingContextVars:
    def test_bound_contextvars_appear_in_record(self, reset_structlog: None):
        configure_logging(log_level="INFO", json_logs=True)
        buffer = _capture_handler_output("")
        logger = structlog.stdlib.get_logger("test_ctx")

        structlog.contextvars.bind_contextvars(request_id="req_xyz", org_id=42)
        logger.info("with_context")

        record = json.loads(buffer.getvalue())
        assert record["request_id"] == "req_xyz"
        assert record["org_id"] == 42

    def test_clear_contextvars_removes_them(self, reset_structlog: None):
        configure_logging(log_level="INFO", json_logs=True)
        buffer = _capture_handler_output("")
        logger = structlog.stdlib.get_logger("test_clear")

        structlog.contextvars.bind_contextvars(request_id="req_abc")
        structlog.contextvars.clear_contextvars()
        logger.info("after_clear")

        record = json.loads(buffer.getvalue())
        assert "request_id" not in record


class TestConfigureLoggingLevel:
    def test_debug_level_emits_debug_records(self, reset_structlog: None):
        configure_logging(log_level="DEBUG", json_logs=True)
        buffer = _capture_handler_output("", level=logging.DEBUG)
        logger = structlog.stdlib.get_logger("test_debug")

        logger.debug("debug_record")

        assert buffer.getvalue(), "DEBUG record should be emitted at DEBUG level"

    def test_warning_level_swallows_info_records(self, reset_structlog: None):
        configure_logging(log_level="WARNING", json_logs=True)
        buffer = _capture_handler_output("", level=logging.WARNING)
        logger = structlog.stdlib.get_logger("test_warn")

        logger.info("info_record")

        assert buffer.getvalue() == "", (
            "INFO record should be filtered out at WARNING level"
        )
