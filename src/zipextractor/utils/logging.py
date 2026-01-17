"""Logging configuration for ZIP Extractor.

This module provides structured JSON logging with rotating file handlers
for the ZIP Extractor application.
"""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, ClassVar

# Log directory
LOG_DIR = Path.home() / ".local" / "share" / "zipextractor" / "logs"
LOG_FILE = "zipextractor.log"
MAX_LOG_SIZE = 10 * 1024 * 1024  # 10 MB
BACKUP_COUNT = 5


class JsonFormatter(logging.Formatter):
    """Custom formatter that outputs JSON-structured log records.

    This formatter produces logs in a structured JSON format that is
    easy to parse and analyze.
    """

    def format(self, record: logging.LogRecord) -> str:
        """Format the log record as JSON.

        Args:
            record: The log record to format.

        Returns:
            JSON-formatted log string.
        """
        log_data: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add extra fields if present
        extra_keys = set(record.__dict__.keys()) - {
            "name",
            "msg",
            "args",
            "created",
            "filename",
            "funcName",
            "levelname",
            "levelno",
            "lineno",
            "module",
            "msecs",
            "pathname",
            "process",
            "processName",
            "relativeCreated",
            "stack_info",
            "exc_info",
            "exc_text",
            "thread",
            "threadName",
            "taskName",
            "message",
        }
        for key in extra_keys:
            log_data[key] = getattr(record, key)

        return json.dumps(log_data, default=str)


class ConsoleFormatter(logging.Formatter):
    """Colored console formatter for development.

    This formatter adds colors to log output for better readability
    in the terminal during development.
    """

    COLORS: ClassVar[dict[str, str]] = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[35m",  # Magenta
    }
    RESET: ClassVar[str] = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        """Format the log record with colors.

        Args:
            record: The log record to format.

        Returns:
            Colored log string.
        """
        color = self.COLORS.get(record.levelname, "")
        timestamp = datetime.now().strftime("%H:%M:%S")
        message = record.getMessage()

        formatted = (
            f"{color}{timestamp} [{record.levelname:8}]{self.RESET} {record.name}: {message}"
        )

        if record.exc_info:
            formatted += "\n" + self.formatException(record.exc_info)

        return formatted


def setup_logging(
    level: int = logging.INFO,
    enable_file_logging: bool = True,
    enable_console_logging: bool = True,
) -> None:
    """Configure application-wide logging.

    Sets up both file-based (JSON) and console (colored) logging handlers.

    Args:
        level: The logging level to use.
        enable_file_logging: Whether to enable file logging.
        enable_console_logging: Whether to enable console logging.
    """
    # Get root logger for the application
    root_logger = logging.getLogger("zipextractor")
    root_logger.setLevel(level)

    # Clear any existing handlers
    root_logger.handlers.clear()

    if enable_file_logging:
        # Ensure log directory exists
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        log_path = LOG_DIR / LOG_FILE

        # File handler with JSON formatting
        file_handler = RotatingFileHandler(
            log_path,
            maxBytes=MAX_LOG_SIZE,
            backupCount=BACKUP_COUNT,
            encoding="utf-8",
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(JsonFormatter())
        root_logger.addHandler(file_handler)

    if enable_console_logging:
        # Console handler with colored output
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setLevel(level)
        console_handler.setFormatter(ConsoleFormatter())
        root_logger.addHandler(console_handler)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance for the given module.

    This function ensures that the logging is properly configured
    before returning a logger.

    Args:
        name: The name of the module requesting the logger.
              Typically __name__ is passed.

    Returns:
        A configured logger instance.
    """
    # Ensure logging is set up on first call
    root_logger = logging.getLogger("zipextractor")
    if not root_logger.handlers:
        setup_logging()

    # Return a child logger
    if name.startswith("zipextractor"):
        return logging.getLogger(name)
    return logging.getLogger(f"zipextractor.{name}")


def set_log_level(level: int | str) -> None:
    """Change the logging level at runtime.

    Args:
        level: The new logging level (int or string like 'DEBUG').
    """
    if isinstance(level, str):
        level = getattr(logging, level.upper(), logging.INFO)

    root_logger = logging.getLogger("zipextractor")
    root_logger.setLevel(level)
    for handler in root_logger.handlers:
        handler.setLevel(level)


def get_log_file_path() -> Path:
    """Get the path to the current log file.

    Returns:
        Path to the log file.
    """
    return LOG_DIR / LOG_FILE
