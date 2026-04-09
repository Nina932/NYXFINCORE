"""
FinAI Backend — Structured JSON Logging Configuration
=======================================================
Replaces default Python logging with structured JSON output.
Every log entry includes: timestamp, level, logger, message,
request_id, user_id, agent_name, duration_ms (when available).

Usage:
    from app.logging_config import setup_logging
    setup_logging()  # Call once at startup in main.py

Individual loggers automatically inherit structured format.
"""
import logging
import logging.config
import sys
import os
from typing import Optional

# ── Try to import python-json-logger; graceful fallback to standard ──────────
try:
    from pythonjsonlogger import jsonlogger
    _JSON_AVAILABLE = True
except ImportError:
    _JSON_AVAILABLE = False


class FinAIJsonFormatter(jsonlogger.JsonFormatter if _JSON_AVAILABLE else logging.Formatter):
    """
    Custom JSON log formatter that adds FinAI-specific fields.
    Every log record gets: timestamp, level, logger, message,
    plus any extra fields passed via logger.info(..., extra={...}).
    """

    def add_fields(self, log_record: dict, record: logging.LogRecord, message_dict: dict):
        super().add_fields(log_record, record, message_dict)
        # Normalize timestamp field name
        if "asctime" in log_record:
            log_record["timestamp"] = log_record.pop("asctime")
        if not log_record.get("timestamp"):
            from datetime import datetime, timezone
            log_record["timestamp"] = datetime.now(timezone.utc).isoformat()
        log_record["level"] = record.levelname
        log_record["logger"] = record.name
        # Include FinAI context fields if present
        for field in ("request_id", "user_id", "agent_name", "duration_ms",
                      "dataset_id", "company_id", "llm_tier", "tokens_used"):
            if hasattr(record, field):
                log_record[field] = getattr(record, field)


def setup_logging(
    log_level: Optional[str] = None,
    log_file: Optional[str] = None,
    force_json: bool = False,
) -> None:
    """
    Configure structured logging for the FinAI platform.

    Args:
        log_level: Override LOG_LEVEL from settings (default: INFO)
        log_file:  Override LOG_FILE from settings
        force_json: Force JSON format even in development

    Call once at application startup:
        from app.logging_config import setup_logging
        setup_logging()
    """
    from app.config import settings

    level_str = (log_level or settings.LOG_LEVEL).upper()
    level = getattr(logging, level_str, logging.INFO)

    log_file_path = log_file or settings.LOG_FILE
    os.makedirs(os.path.dirname(log_file_path) if os.path.dirname(log_file_path) else ".", exist_ok=True)

    # Use JSON in production or when explicitly forced; plain text in dev
    use_json = _JSON_AVAILABLE and (force_json or settings.APP_ENV != "development")

    if use_json:
        fmt = FinAIJsonFormatter(
            fmt="%(timestamp)s %(level)s %(logger)s %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )
    else:
        # Developer-friendly format with colours via standard formatter
        fmt = logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)-40s | %(message)s",
            datefmt="%H:%M:%S",
        )

    # ── Handlers ─────────────────────────────────────────────────────────────
    handlers: list[logging.Handler] = []

    # Console handler
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(fmt)
    console.setLevel(level)
    handlers.append(console)

    # Rotating file handler
    try:
        from logging.handlers import RotatingFileHandler
        file_handler = RotatingFileHandler(
            log_file_path,
            maxBytes=50 * 1024 * 1024,   # 50MB per file
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setFormatter(fmt)
        file_handler.setLevel(level)
        handlers.append(file_handler)
    except Exception as e:
        print(f"[logging_config] Could not create file handler: {e}", file=sys.stderr)

    # ── Root logger ───────────────────────────────────────────────────────────
    root = logging.getLogger()
    root.setLevel(level)
    # Remove existing handlers to avoid duplicates on hot-reload
    root.handlers.clear()
    for h in handlers:
        root.addHandler(h)

    # ── Silence noisy third-party loggers ─────────────────────────────────────
    for noisy in (
        "uvicorn.access",      # per-request HTTP logs at INFO → WARNING
        "sqlalchemy.engine",   # SQL echo → only on DEBUG
        "sqlalchemy.pool",
        "httpx",
        "httpcore",
        "chromadb",
        "openai",
        "anthropic",
    ):
        logging.getLogger(noisy).setLevel(
            logging.WARNING if level <= logging.INFO else level
        )

    # Restore uvicorn.error to full level (we want startup errors)
    logging.getLogger("uvicorn.error").setLevel(level)

    logging.getLogger(__name__).info(
        "Logging configured: level=%s format=%s file=%s json_available=%s",
        level_str, "json" if use_json else "text", log_file_path, _JSON_AVAILABLE,
    )


class RequestLogContext:
    """
    Context manager / helper to attach FinAI fields to log records.

    Usage in middleware:
        with RequestLogContext(request_id="abc", user_id="u1"):
            logger.info("Processing request")  # will include request_id, user_id
    """
    _local_fields: dict = {}

    @classmethod
    def set(cls, **kwargs) -> None:
        cls._local_fields.update(kwargs)

    @classmethod
    def clear(cls) -> None:
        cls._local_fields.clear()

    @classmethod
    def get(cls) -> dict:
        return dict(cls._local_fields)


class FinAILoggerAdapter(logging.LoggerAdapter):
    """
    LoggerAdapter that automatically includes FinAI context fields.

    Usage:
        from app.logging_config import get_logger
        logger = get_logger(__name__, agent_name="CalcAgent")
        logger.info("Calculation complete", extra={"duration_ms": 42})
    """
    def process(self, msg, kwargs):
        extra = kwargs.setdefault("extra", {})
        extra.update(self.extra)
        extra.update(RequestLogContext.get())
        return msg, kwargs


def get_logger(name: str, **context_fields) -> FinAILoggerAdapter:
    """
    Get a FinAI-aware logger with optional built-in context fields.

    Args:
        name: Logger name (use __name__)
        **context_fields: Fields always included in this logger's records
                          (e.g., agent_name="CalcAgent", component="gl_pipeline")

    Returns:
        FinAILoggerAdapter that emits structured logs with context.
    """
    base_logger = logging.getLogger(name)
    return FinAILoggerAdapter(base_logger, context_fields)
