"""Test logging module."""

import logging
import os
import re

import pytest

from src.core.logger import (
    ColoredFormatter,
    LogColors,
    apply_log_level,
    get_log_dir,
    get_logger,
    setup_logger,
)


class TestSetupLogger:
    def test_returns_logger_instance(self):
        logger = setup_logger("MySnipaste")
        assert isinstance(logger, logging.Logger)

    def test_main_logger_name(self):
        logger = setup_logger("MySnipaste")
        assert logger.name == "MySnipaste"

    def test_sub_logger_has_correct_name(self):
        sub = setup_logger("ocr")
        assert sub.name == "MySnipaste.ocr"

    def test_sub_logger_inherits_handlers(self):
        """A sub-logger should propagate to the parent logger (no duplicate handlers)."""
        main = setup_logger("MySnipaste")
        sub = setup_logger("ocr")
        # Sub-logger should not have its own handlers (inherits from parent)
        assert len(sub.handlers) == 0
        assert sub.propagate is True

    def test_setup_twice_returns_same_instance(self):
        """Calling setup_logger twice for the same name should not duplicate handlers."""
        first = setup_logger("MySnipaste")
        second = setup_logger("MySnipaste")
        assert first is second

    def test_level_is_debug_by_default(self):
        logger = setup_logger("MySnipaste")
        assert logger.level == logging.DEBUG


class TestGetLogger:
    def test_returns_child_logger(self):
        logger = get_logger("test")
        assert isinstance(logger, logging.Logger)
        assert logger.name == "MySnipaste.test"


class TestApplyLogLevel:
    def test_apply_debug(self, monkeypatch):
        monkeypatch.setattr("src.core.logger.logger", logging.getLogger("MySnipaste"))
        apply_log_level("DEBUG")
        assert logging.getLogger("MySnipaste").level <= logging.DEBUG

    def test_apply_info(self, monkeypatch):
        monkeypatch.setattr("src.core.logger.logger", logging.getLogger("MySnipaste"))
        apply_log_level("INFO")
        logger = logging.getLogger("MySnipaste")
        assert logger.level == logging.INFO

    def test_apply_warning(self, monkeypatch):
        monkeypatch.setattr("src.core.logger.logger", logging.getLogger("MySnipaste"))
        apply_log_level("WARNING")
        assert logging.getLogger("MySnipaste").level == logging.WARNING

    def test_apply_error(self, monkeypatch):
        monkeypatch.setattr("src.core.logger.logger", logging.getLogger("MySnipaste"))
        apply_log_level("ERROR")
        assert logging.getLogger("MySnipaste").level == logging.ERROR

    def test_unknown_level_defaults_to_debug(self, monkeypatch):
        monkeypatch.setattr("src.core.logger.logger", logging.getLogger("MySnipaste"))
        apply_log_level("INVALID_LEVEL")
        assert logging.getLogger("MySnipaste").level == logging.DEBUG


class TestColoredFormatter:
    def test_format_includes_level_color(self):
        """ColoredFormatter should inject ANSI color codes into the levelname."""
        fmt = ColoredFormatter(datefmt="%H:%M:%S")
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname=__file__,
            lineno=42,
            msg="hello",
            args=(),
            exc_info=None,
        )
        formatted = fmt.format(record)
        # Should contain the green color code for INFO
        assert LogColors.INFO in formatted
        assert "hello" in formatted
        # levelname should be restored after formatting
        assert record.levelname == "INFO"

    def test_format_error_includes_exc_info(self):
        fmt = ColoredFormatter(datefmt="%H:%M:%S")
        try:
            raise ValueError("test error")
        except ValueError:
            import sys
            exc_info = sys.exc_info()
        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname=__file__,
            lineno=99,
            msg="oops",
            args=(),
            exc_info=exc_info,
        )
        formatted = fmt.format(record)
        assert "ValueError" in formatted
        assert "test error" in formatted


class TestLogColors:
    def test_all_colors_defined(self):
        assert LogColors.RESET.startswith("\033[")
        assert LogColors.DEBUG.startswith("\033[")
        assert LogColors.INFO.startswith("\033[")
        assert LogColors.WARNING.startswith("\033[")
        assert LogColors.ERROR.startswith("\033[")
        assert LogColors.CRITICAL.startswith("\033[")
        assert LogColors.TIME.startswith("\033[")
        assert LogColors.NAME.startswith("\033[")

    def test_reset_closes_ansi(self):
        assert LogColors.RESET == "\033[0m"
