"""Unit tests for src._core.infrastructure.observability.otel_setup.

These tests clean up the global TracerProvider so they do not leak
BatchSpanProcessor threads or pollute downstream tests.
"""

from __future__ import annotations

import contextlib
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

# Skip entire module when otel extra is not installed.
pytest.importorskip("opentelemetry.sdk.trace")
pytest.importorskip("opentelemetry.exporter.otlp.proto.grpc.trace_exporter")

# Patch target: use the name bound in otel_setup's namespace, not the origin.
_EXPORTER_PATCH = "src._core.infrastructure.observability.otel_setup.OTLPSpanExporter"


@pytest.fixture(autouse=True)
def reset_tracer_provider():
    """Reset the global TracerProvider before and after each test.

    opentelemetry-api 1.40+ default state: _TRACER_PROVIDER = None (the
    ProxyTracerProvider is returned by get_tracer_provider() only when
    _TRACER_PROVIDER is None). A private _TRACER_PROVIDER_SET_ONCE guard
    rejects subsequent calls once a real provider is installed — we must
    reset both the once-flag AND the reference to None to restore defaults.
    """
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider as SdkTracerProvider

    def _reset() -> None:
        existing = getattr(trace, "_TRACER_PROVIDER", None)
        if isinstance(existing, SdkTracerProvider):
            with contextlib.suppress(Exception):
                existing.shutdown()
        trace._TRACER_PROVIDER_SET_ONCE._done = False  # type: ignore[attr-defined]
        trace._TRACER_PROVIDER = None  # type: ignore[attr-defined]

    _reset()
    yield
    _reset()


def _make_fake_settings(endpoint: str = "http://localhost:4317") -> MagicMock:
    s = MagicMock()
    s.otel_enabled = True
    s.otel_exporter_otlp_endpoint = endpoint
    return s


class TestConfigureOtel:
    def test_sets_real_tracer_provider(self):
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.trace import ProxyTracerProvider

        from src._core.infrastructure.observability.otel_setup import configure_otel

        assert isinstance(trace.get_tracer_provider(), ProxyTracerProvider)

        with patch(_EXPORTER_PATCH):
            configure_otel(_make_fake_settings(), service_name="test-svc")

        assert isinstance(trace.get_tracer_provider(), TracerProvider)

    def test_idempotent_skips_provider_setup_when_already_configured(self):
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider

        from src._core.infrastructure.observability.otel_setup import configure_otel

        with patch(_EXPORTER_PATCH):
            configure_otel(_make_fake_settings(), service_name="first-call")

        first_provider = trace.get_tracer_provider()
        assert isinstance(first_provider, TracerProvider)

        with patch(_EXPORTER_PATCH) as mock_exp:
            configure_otel(_make_fake_settings(), service_name="second-call")

        # Exporter constructor was NOT called on the second pass.
        mock_exp.assert_not_called()
        # Provider is the same object.
        assert trace.get_tracer_provider() is first_provider

    def test_service_name_env_override_wins(self, monkeypatch: pytest.MonkeyPatch):
        """OTEL_SERVICE_NAME env var must take precedence over the code default."""
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider

        from src._core.infrastructure.observability.otel_setup import configure_otel

        monkeypatch.setenv("OTEL_SERVICE_NAME", "my-custom-service")

        with patch(_EXPORTER_PATCH):
            configure_otel(_make_fake_settings(), service_name="blueprint-default")

        provider = trace.get_tracer_provider()
        assert isinstance(provider, TracerProvider)
        # SDK picks up OTEL_SERVICE_NAME from env; code-default must NOT override it.
        service_name = provider.resource.attributes.get("service.name")
        assert service_name == "my-custom-service"

    def test_skips_pydantic_ai_when_module_missing(self):
        """_instrument_pydantic_ai_agents emits warning and returns when pydantic_ai absent."""
        import logging

        from src._core.infrastructure.observability.otel_setup import (
            _instrument_pydantic_ai_agents,
        )

        pydantic_ai_err = ModuleNotFoundError("No module named 'pydantic_ai'")
        pydantic_ai_err.name = "pydantic_ai"

        with patch.dict(sys.modules, {"pydantic_ai": None}):
            # Must not raise — missing extra is a warning, not an error.
            _instrument_pydantic_ai_agents()

    def test_propagates_non_pydantic_ai_module_not_found(self):
        """An ImportError from our own code (typo etc.) must NOT be swallowed."""
        from src._core.infrastructure.observability.otel_setup import (
            _instrument_pydantic_ai_agents,
        )

        unrelated_err = ModuleNotFoundError("No module named 'some_other_lib'")
        unrelated_err.name = "some_other_lib"

        with patch(
            "builtins.__import__",
            side_effect=lambda name, *a, **kw: (
                (_ for _ in ()).throw(unrelated_err)  # type: ignore[misc]
                if name == "pydantic_ai"
                else __import__(name, *a, **kw)
            ),
        ):
            with pytest.raises(ModuleNotFoundError, match="some_other_lib"):
                _instrument_pydantic_ai_agents()
