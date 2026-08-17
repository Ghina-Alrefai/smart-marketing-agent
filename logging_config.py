"""Central application logging with per-request trace identifiers."""

from __future__ import annotations

import logging
import re
import sys
import uuid
from contextvars import ContextVar
from logging.handlers import RotatingFileHandler
from pathlib import Path

from config import settings


_request_id: ContextVar[str] = ContextVar("request_id", default="-")


class RequestIdFilter(logging.Filter):
    """Attach the active request identifier to every application log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = _request_id.get()
        return True


def new_request_id(value: str | None = None) -> str:
    """Return a safe client-supplied ID or generate a new compact trace ID."""

    if value:
        cleaned = re.sub(r"[^A-Za-z0-9_.-]", "_", value.strip())[:64]
        if cleaned:
            return cleaned
    return uuid.uuid4().hex[:16]


def bind_request_id(request_id: str):
    return _request_id.set(request_id)


def reset_request_id(token) -> None:
    _request_id.reset(token)


def get_request_id() -> str:
    return _request_id.get()


def configure_logging() -> logging.Logger:
    """Configure console and rotating-file handlers once and return app logger."""

    logger = logging.getLogger("smartsocial")
    level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    logger.setLevel(level)
    logger.propagate = False

    if getattr(logger, "_smartsocial_configured", False):
        return logger

    log_filter = RequestIdFilter()
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | request_id=%(request_id)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console = logging.StreamHandler(sys.stdout)
    console.setLevel(level)
    console.setFormatter(formatter)
    console.addFilter(log_filter)
    logger.addHandler(console)

    if settings.LOG_TO_FILE:
        try:
            log_dir = Path(settings.LOG_DIR)
            log_dir.mkdir(parents=True, exist_ok=True)
            file_handler = RotatingFileHandler(
                log_dir / "app.log",
                maxBytes=settings.LOG_MAX_BYTES,
                backupCount=settings.LOG_BACKUP_COUNT,
                encoding="utf-8",
            )
            file_handler.setLevel(level)
            file_handler.setFormatter(formatter)
            file_handler.addFilter(log_filter)
            logger.addHandler(file_handler)
        except OSError as exc:
            logger.warning(
                "logging.file_disabled path=%s error_type=%s",
                settings.LOG_DIR,
                type(exc).__name__,
            )

    logging.captureWarnings(True)
    logger._smartsocial_configured = True
    logger.info(
        "logging.configured level=%s file_enabled=%s log_dir=%s environment=%s",
        logging.getLevelName(level),
        settings.LOG_TO_FILE,
        settings.LOG_DIR,
        settings.APP_ENV,
    )
    return logger
