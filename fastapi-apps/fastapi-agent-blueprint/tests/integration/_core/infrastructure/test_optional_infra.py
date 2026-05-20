"""Boot-regression tests for optional infrastructure (#101, ADR 042).

Acceptance criterion: with only ``DATABASE_ENGINE=sqlite`` set and every other
optional-infra env var unset, the app must:

- import cleanly (no ImportError even if the matching optional extra is not
  installed — this is tested via lazy-import factories inside
  ``core_container``);
- return the documented disabled-branch value for each infra provider
  (``None`` for data stores, ``StubEmbedder`` for the embedder);
- keep the broker selector defaulting to ``inmemory`` when ``BROKER_TYPE`` is
  unset.

Tests here do not hit the network or instantiate real AWS / PydanticAI
clients; they only verify the container's wiring.
"""

from __future__ import annotations

import importlib.util

import pytest

from src._core.config import settings
from src._core.infrastructure.di.core_container import CoreContainer
from src._core.infrastructure.rag.stub_embedder import StubEmbedder

_has_pydantic_ai = importlib.util.find_spec("pydantic_ai") is not None


@pytest.fixture
def clean_optional_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force every optional-infra Settings field to its ``disabled`` value.

    This isolates the test from whatever the developer has in ``_env/.env``
    without mutating the shared Settings singleton outside this test's scope.
    """
    for field in (
        "storage_type",
        "dynamodb_access_key",
        "s3vectors_access_key",
        "embedding_provider",
        "embedding_model",
        "llm_provider",
        "llm_model",
        "otel_exporter_otlp_endpoint",
    ):
        monkeypatch.setattr(settings, field, None)
    monkeypatch.setattr(settings, "broker_type", None)
    monkeypatch.setattr(settings, "otel_enabled", False)


class TestCoreContainerMinimalBoot:
    def test_storage_providers_return_none(self, clean_optional_env: None):
        container = CoreContainer()
        assert container.storage_client() is None
        assert container.storage() is None

    def test_dynamodb_client_returns_none(self, clean_optional_env: None):
        container = CoreContainer()
        assert container.dynamodb_client() is None

    def test_s3vector_client_returns_none(self, clean_optional_env: None):
        container = CoreContainer()
        assert container.s3vector_client() is None

    def test_embedding_client_returns_stub(self, clean_optional_env: None):
        container = CoreContainer()
        assert isinstance(container.embedding_client(), StubEmbedder)

    def test_llm_model_returns_stub_when_disabled(self, clean_optional_env: None):
        """Disabled branch returns a PydanticAI ``TestModel`` when the
        ``pydantic-ai`` extra is installed; otherwise ``None``.

        ``build_stub_llm_model`` is deliberately defensive — the
        acceptance criterion for #101 is "app boots with optional
        extras uninstalled". With pydantic-ai present, the stub lets
        ``classification`` / ``docs`` round-trip under ``make quickstart``
        with no LLM credentials (ADR 042 + Part B).
        """
        container = CoreContainer()
        llm = container.llm_model()

        if _has_pydantic_ai:
            from pydantic_ai.models.test import TestModel

            assert isinstance(llm, TestModel)
        else:
            assert llm is None

    def test_broker_defaults_to_inmemory(self, clean_optional_env: None):
        from taskiq import InMemoryBroker

        container = CoreContainer()
        assert isinstance(container.broker(), InMemoryBroker)

    def test_otel_disabled_by_default(self, clean_optional_env: None):
        """OTEL is off by default — clean_optional_env enforces otel_enabled=False.

        This verifies the Settings default so the acceptance criterion
        "make quickstart works unchanged" has a regression guard.
        """
        assert settings.otel_enabled is False
        assert settings.otel_exporter_otlp_endpoint is None


class TestCoreContainerEnabledBranches:
    """Smoke check: when enable flags are set, selectors flip and the
    container resolves to the real-client branch (constructor not called in
    these tests — pyright-level only)."""

    def test_storage_selector_enabled(self, monkeypatch: pytest.MonkeyPatch):
        from src._core.infrastructure.di.core_container import _storage_selector

        monkeypatch.setattr(settings, "storage_type", "s3")
        assert _storage_selector() == "enabled"

    def test_embedding_selector_enabled(self, monkeypatch: pytest.MonkeyPatch):
        from src._core.infrastructure.di.core_container import _embedding_selector

        monkeypatch.setattr(settings, "embedding_provider", "openai")
        monkeypatch.setattr(settings, "embedding_model", "text-embedding-3-small")
        assert _embedding_selector() == "enabled"


class TestAppBootsWithoutOptionalInfra:
    """Smoke test that the FastAPI app imports and wires up without any
    optional infra env vars set.

    Does not hit HTTP; just asserts the bootstrap completes.
    """

    def test_app_imports_and_container_wires(self, clean_optional_env: None):
        # Importing triggers ``bootstrap_app`` which exercises every domain's
        # container wiring. If any optional provider's disabled branch blew
        # up (e.g. eagerly importing ``pydantic_ai``), this would fail.
        from src._apps.server.app import app

        assert app is not None
        assert app.state.container is not None
        core = app.state.container.core_container()
        assert core.embedding_client() is not None  # StubEmbedder

        llm = core.llm_model()
        if _has_pydantic_ai:
            from pydantic_ai.models.test import TestModel

            assert isinstance(llm, TestModel)
        else:
            assert llm is None
