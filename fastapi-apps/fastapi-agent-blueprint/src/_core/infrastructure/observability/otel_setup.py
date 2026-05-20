"""OpenTelemetry tracing setup for PydanticAI Agents.

Called from server/worker bootstrap when settings.otel_enabled is True.
Installs a global TracerProvider with an OTLP gRPC exporter, then calls
Agent.instrument_all() so all PydanticAI Agent instances (existing AND
subsequent) emit GenAI semantic-convention spans.

Module-top imports are intentional — this module is imported lazily
from _maybe_configure_otel() inside a try/except ModuleNotFoundError,
so missing extras surface as a structured log line at bootstrap, not
an import-time crash.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import structlog
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import ProxyTracerProvider

if TYPE_CHECKING:
    from src._core.config import Settings

_logger = structlog.stdlib.get_logger(__name__)


def configure_otel(settings: Settings, service_name: str) -> None:
    """Wire a global TracerProvider + OTLP gRPC exporter, then patch PydanticAI.

    Pre-condition: settings.otel_enabled is True and
    settings.otel_exporter_otlp_endpoint is set (validated in Settings).

    Idempotent — if any non-proxy TracerProvider is already installed
    (Logfire, a previous configure_otel call, or any third-party provider),
    we re-run Agent.instrument_all() (class-level patch — safe to re-apply
    in pydantic-ai 1.83+) but skip the provider/exporter setup so we don't
    fight the existing provider or leak BatchSpanProcessor threads.
    """
    current = trace.get_tracer_provider()
    if not isinstance(current, ProxyTracerProvider):
        _instrument_pydantic_ai_agents()
        _logger.info("otel_already_configured", service_name=service_name)
        return

    # OTel SDK 1.40+ merges env-detected resource first, then code attributes.
    # If we always pass service_name we'd override OTEL_SERVICE_NAME.
    # Honour env override by only setting service.name when the env is silent.
    env_has_service_name = bool(
        os.environ.get("OTEL_SERVICE_NAME")
        or "service.name" in (os.environ.get("OTEL_RESOURCE_ATTRIBUTES") or "")
    )
    resource_attrs: dict[str, str] = {}
    if not env_has_service_name:
        resource_attrs["service.name"] = service_name
    resource = Resource.create(resource_attrs)

    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(endpoint=settings.otel_exporter_otlp_endpoint)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    _instrument_pydantic_ai_agents()
    _logger.info(
        "otel_configured",
        endpoint=settings.otel_exporter_otlp_endpoint,
        service_name=service_name if not env_has_service_name else "(env override)",
    )


def _instrument_pydantic_ai_agents() -> None:
    """Best-effort PydanticAI patch.

    OTEL_ENABLED=true is useful even without pydantic-ai (future
    instrumentation can attach to the same TracerProvider), so a missing
    pydantic-ai extra emits a warning rather than failing.
    """
    try:
        from pydantic_ai import Agent
    except ModuleNotFoundError as exc:
        if exc.name != "pydantic_ai":
            raise
        _logger.warning(
            "otel_pydantic_ai_instrumentation_skipped",
            reason="pydantic_ai_not_installed",
            install_hint="uv sync --extra pydantic-ai",
        )
        return
    Agent.instrument_all()
