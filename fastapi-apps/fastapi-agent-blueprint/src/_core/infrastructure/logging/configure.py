"""structlog configuration entry point (#9).

Called once at app startup — ``bootstrap_app`` for the server,
``_apps/worker/app.py`` import time for the worker. After
``configure_logging()`` runs, ``structlog.get_logger(__name__)`` and
``logging.getLogger(__name__)`` both emit records through the same
pipeline (dev: coloured console; prod: single-line JSON).

Design notes:

- ``shared_processors`` are what every log record passes through before
  rendering. ``merge_contextvars`` must run first so per-request /
  per-task bindings (request_id, task_id, etc.) reach downstream
  processors and the final renderer.

- The existing ``logging.getLogger`` call sites across the codebase
  are left untouched; ``structlog.stdlib.ProcessorFormatter`` with a
  ``foreign_pre_chain`` bridges them into the same pipeline.

- ``cache_logger_on_first_use=True`` is the documented perf default.

- Uvicorn's own loggers (``uvicorn``, ``uvicorn.error``) propagate to
  root and render through this formatter; ``uvicorn.access`` is
  silenced so the ASGI access-log middleware in this package owns the
  request/response log shape.

Background: issue #9.
"""

from __future__ import annotations

import logging
import logging.config
import sys
from typing import Any

import structlog


def _add_request_id(
    logger: Any, method_name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """Inject ``request_id`` from asgi-correlation-id's contextvar.

    ``asgi-correlation-id`` uses its own ``ContextVar`` instance, separate
    from structlog's. Read it here and splice into the event dict so
    every record emitted during a request carries the same request ID
    whether the caller used ``structlog.contextvars.bind_contextvars``
    or just plain stdlib ``logger.info(...)``.
    """
    try:
        from asgi_correlation_id import correlation_id
    except ImportError:
        return event_dict

    rid = correlation_id.get()
    if rid:
        event_dict.setdefault("request_id", rid)
    return event_dict


def _build_shared_processors() -> list[Any]:
    """Processors applied to both structlog-native and stdlib records."""
    return [
        structlog.contextvars.merge_contextvars,
        _add_request_id,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]


def _silence_duplicate_sqlalchemy_handlers() -> None:
    """Strip SQLAlchemy-added handlers so engine logs aren't emitted twice.

    When ``echo=True`` (or ``echo="debug"``) is passed to ``create_engine``,
    SQLAlchemy attaches its own ``StreamHandler`` to the
    ``sqlalchemy.engine`` logger. That handler fires in parallel with the
    root handler configured here, producing two log lines per query —
    one in the default Python format, one through our structlog pipeline.

    Clearing the handlers (and leaving ``propagate=True``) routes every
    engine record through the structlog pipeline exactly once.
    """
    for name in ("sqlalchemy.engine", "sqlalchemy.engine.Engine"):
        logger = logging.getLogger(name)
        logger.handlers.clear()
        logger.propagate = True


def _build_dict_config(
    level_value: int,
    shared_processors: list[Any],
    renderer: Any,
) -> dict[str, Any]:
    """Build the stdlib ``logging.config.dictConfig`` payload."""
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "structlog": {
                "()": structlog.stdlib.ProcessorFormatter,
                "foreign_pre_chain": shared_processors,
                "processors": [
                    structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                    renderer,
                ],
            },
        },
        "handlers": {
            "default": {
                "class": "logging.StreamHandler",
                "formatter": "structlog",
                "stream": "ext://sys.stdout",
            },
        },
        "loggers": {
            # Root — catches every stdlib logger that does not have its
            # own handler. Every ``logging.getLogger(__name__)`` call in
            # the codebase propagates here.
            "": {
                "handlers": ["default"],
                "level": level_value,
                "propagate": False,
            },
            # Uvicorn's framework logs: keep as-is, let them ride root.
            "uvicorn": {"handlers": [], "level": level_value, "propagate": True},
            "uvicorn.error": {
                "handlers": [],
                "level": level_value,
                "propagate": True,
            },
            # Silence uvicorn's built-in access log — the ASGI access
            # middleware replaces it with structured request/response
            # records. Keeping both would duplicate every request line.
            "uvicorn.access": {
                "handlers": [],
                "level": logging.WARNING,
                "propagate": False,
            },
            # SQLAlchemy engine echo routes through the root handler
            # (level honours DATABASE_ECHO). Cleared below to drop any
            # handler SQLAlchemy attached during ``create_engine``.
            "sqlalchemy.engine": {
                "handlers": [],
                "level": level_value,
                "propagate": True,
            },
        },
    }


def configure_logging(*, log_level: str = "INFO", json_logs: bool = False) -> None:
    """Configure structlog + stdlib logging to share a single pipeline.

    Args:
        log_level: Root log level (e.g. ``"INFO"``, ``"DEBUG"``). Applied
            to both structlog-originated records and stdlib loggers.
        json_logs: ``True`` emits single-line JSON (prod / shipping to
            log aggregators). ``False`` emits coloured console output
            (dev).
    """
    shared_processors = _build_shared_processors()
    renderer: Any = (
        structlog.processors.JSONRenderer()
        if json_logs
        else structlog.dev.ConsoleRenderer(colors=sys.stdout.isatty())
    )

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    level_value = logging.getLevelNamesMapping().get(log_level.upper(), logging.INFO)
    logging.config.dictConfig(
        _build_dict_config(level_value, shared_processors, renderer)
    )
    _silence_duplicate_sqlalchemy_handlers()
