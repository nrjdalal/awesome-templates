"""The guarded entry point into OpenTelemetry setup, shared by every process.

Separate from ``otel_setup`` on purpose. ``otel_setup`` imports the
``opentelemetry`` packages at module top, so it is the thing being guarded and
cannot host its own guard — importing this module must stay cheap and safe when
the ``otel`` extra is not installed.

Server and worker bootstrap each carried a byte-for-byte copy of this function,
differing only in whether the docstring said "server" or "worker" (#331).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from src._core.config import Settings

_logger = structlog.stdlib.get_logger(__name__)


def maybe_configure_otel(settings: Settings, service_name: str) -> None:
    """Configure OpenTelemetry tracing if enabled and the otel extra is installed.

    If the extra is missing the process still boots; the skip is recorded as a
    structured log line so operators can diagnose without re-reading the README.

    ``settings`` is a parameter rather than a module-level import because the two
    call sites read it from their own app module's scope.
    """
    if not settings.otel_enabled:
        return
    try:
        from src._core.infrastructure.observability.otel_setup import configure_otel
    except ModuleNotFoundError as exc:
        if exc.name and not exc.name.startswith("opentelemetry"):
            raise
        _logger.warning(
            "otel_extra_not_installed",
            install_hint="uv sync --extra otel",
        )
        return
    configure_otel(settings, service_name=service_name)
