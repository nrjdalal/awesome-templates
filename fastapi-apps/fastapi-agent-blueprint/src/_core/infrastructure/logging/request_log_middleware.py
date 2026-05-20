"""ASGI middleware that emits one structured record per HTTP request (#9).

Registered after ``asgi_correlation_id.CorrelationIdMiddleware`` — the
correlation ID is already bound into ``contextvars`` by the time this
middleware runs, so the emitted record automatically carries
``request_id`` via ``structlog.contextvars.merge_contextvars``.

Using a **class-based ASGI middleware** (not ``@app.middleware("http")``)
is deliberate: ``BaseHTTPMiddleware`` uses a child task group for the
endpoint, which breaks ``contextvars`` propagation on exit. Staying on
pure ASGI keeps a single context visible across the whole request.
(Background: https://github.com/fastapi/fastapi/issues/4696.)
"""

from __future__ import annotations

import time
from typing import Any

import structlog
from starlette.types import ASGIApp, Message, Receive, Scope, Send


class RequestLogMiddleware:
    """Log one ``http_request`` record per HTTP request."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self._logger = structlog.stdlib.get_logger("src._core.infrastructure.logging")

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "")
        path = scope.get("path", "")
        start = time.perf_counter()

        status_holder: dict[str, int] = {"code": 0}

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                status_holder["code"] = int(message.get("status", 0))
            await send(message)

        structlog.contextvars.bind_contextvars(
            http_method=method,
            http_path=path,
        )
        try:
            await self.app(scope, receive, send_wrapper)
        except Exception:
            duration_ms = (time.perf_counter() - start) * 1000
            self._logger.exception(
                "http_request_failed",
                duration_ms=round(duration_ms, 2),
                status_code=status_holder["code"] or 500,
            )
            raise
        else:
            duration_ms = (time.perf_counter() - start) * 1000
            log_method = (
                self._logger.warning
                if status_holder["code"] >= 500
                else self._logger.info
            )
            log_method(
                "http_request",
                duration_ms=round(duration_ms, 2),
                status_code=status_holder["code"],
            )
        finally:
            # Unbind per-request keys so the worker thread / next request
            # starts clean. ``clear_contextvars`` would wipe everything
            # including anything the caller bound *around* this request;
            # remove only the keys this middleware owns.
            _unbind_if_present("http_method", "http_path")


def _unbind_if_present(*keys: str) -> None:
    """Remove keys from the current context without crashing on absence."""
    current: dict[str, Any] = dict(structlog.contextvars.get_contextvars())
    for key in keys:
        current.pop(key, None)
    structlog.contextvars.clear_contextvars()
    if current:
        structlog.contextvars.bind_contextvars(**current)
