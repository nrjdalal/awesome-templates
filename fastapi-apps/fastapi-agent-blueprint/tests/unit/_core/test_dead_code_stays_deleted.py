"""The #331 deletions, pinned so they are not reintroduced.

Cluster G removed eleven symbols that nothing referenced *and* that no document
advertised as an extension point. That second half is the whole test: this repo
deliberately ships base classes and stub fallbacks with zero implementers
(README, project-dna §0 dual audience, ADR 042), so a reference count alone is
never grounds for deletion here.

Three candidates from the same issue were therefore **kept**, and they are
pinned too — a later reader working from the issue text would otherwise delete
them on the issue's authority:

- ``BUSINESS_CONFLICT`` is the default ``error_code`` of the public
  ``raise_if_errors(status_code=409)`` path, so a name search finds no callers.
- ``build_stub_llm_model`` is live production wiring — the ``disabled`` branch of
  ``CoreContainer.llm_model`` (ADR 042).
- ``BaseDynamoService`` has zero implementers and stays, which #331 states
  explicitly.
"""

from __future__ import annotations

import importlib

import pytest

_DELETED_MODULES = [
    "src._core.infrastructure.taskiq.manager",
    "src._core.infrastructure.http.base_http_gateway",
    "src._core.infrastructure.http.example_gateway",
    "src._core.infrastructure.llm.exceptions",
    "src.classification.domain.exceptions.classification_exceptions",
]

_DELETED_SYMBOLS = [
    ("src._core.infrastructure.taskiq.broker", "BrokerType"),
    ("src._core.application.dtos.base_response", "ExistsData"),
    ("src._core.application.dtos.base_config", "InternalConfig"),
    ("src._core.application.dtos.base_config", "INTERNAL_CONFIG"),
    ("src._core.infrastructure.vectors.s3.exceptions", "S3VectorNotFoundException"),
    (
        "src.admin_identity.domain.exceptions.admin_identity_exceptions",
        "AdminPermissionDeniedException",
    ),
    # Thin `raise_if_errors(collect_*(...))` wrappers with no callers. The
    # `collect_*` functions they wrapped are alive and widely used, which is why
    # deleting the wrappers orphaned neither them nor the documented repository
    # read primitives (`exists_by_fields`, `existing_values_by_field`).
    ("src._core.domain.validation", "ensure_no_duplicate_field_values"),
    ("src._core.domain.validation", "ensure_unique_field_values"),
    ("src._core.domain.validation", "ensure_unique_field_values_for_batch"),
]


@pytest.mark.parametrize("dotted", _DELETED_MODULES)
def test_the_module_is_gone(dotted: str) -> None:
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(dotted)


@pytest.mark.parametrize(("dotted", "symbol"), _DELETED_SYMBOLS)
def test_the_symbol_is_gone(dotted: str, symbol: str) -> None:
    module = importlib.import_module(dotted)

    assert not hasattr(module, symbol)


def test_the_container_no_longer_wires_a_taskiq_manager() -> None:
    from src._core.infrastructure.di.core_container import CoreContainer

    assert not hasattr(CoreContainer, "taskiq_manager")


class TestKeptOnPurpose:
    def test_business_conflict_is_the_409_default(self) -> None:
        from src._core.domain.validation import (
            BUSINESS_CONFLICT,
            ValidationErrorDetail,
            raise_if_errors,
        )

        errors = [ValidationErrorDetail(field="x", message="dup", type="unique")]
        with pytest.raises(Exception) as exc:  # noqa: B017 - identity checked below
            raise_if_errors(errors, status_code=409)

        assert exc.value.error_code == BUSINESS_CONFLICT

    def test_the_422_default_is_unchanged(self) -> None:
        from src._core.domain.validation import (
            BUSINESS_VALIDATION_ERROR,
            ValidationErrorDetail,
            raise_if_errors,
        )

        errors = [ValidationErrorDetail(field="x", message="bad", type="value")]
        with pytest.raises(Exception) as exc:  # noqa: B017 - identity checked below
            raise_if_errors(errors)

        assert exc.value.error_code == BUSINESS_VALIDATION_ERROR

    def test_build_stub_llm_model_is_still_wired(self) -> None:
        from src._core.infrastructure.llm.stub_llm_model import build_stub_llm_model

        assert callable(build_stub_llm_model)

    def test_base_dynamo_service_is_kept_despite_zero_implementers(self) -> None:
        from src._core.domain.services.base_dynamo_service import BaseDynamoService

        assert BaseDynamoService is not None


class TestOtelGuardCollapsedIntoOneHome:
    def test_neither_bootstrap_keeps_a_private_copy(self) -> None:
        from src._apps.server import bootstrap as server_bootstrap
        from src._apps.worker import bootstrap as worker_bootstrap

        assert not hasattr(server_bootstrap, "_maybe_configure_otel")
        assert not hasattr(worker_bootstrap, "_maybe_configure_otel")

    def test_the_shared_guard_is_not_in_the_module_it_guards(self) -> None:
        """`otel_setup` imports opentelemetry at module top.

        Hosting the guard there would mean importing the guarded package to
        reach the guard, which is the one thing the guard exists to avoid.
        """
        from src._core.infrastructure.observability import otel_bootstrap

        assert callable(otel_bootstrap.maybe_configure_otel)
        assert not hasattr(otel_bootstrap, "OTLPSpanExporter")

    def test_it_is_a_noop_when_otel_is_disabled(self) -> None:
        from src._core.infrastructure.observability.otel_bootstrap import (
            maybe_configure_otel,
        )

        class _Settings:
            otel_enabled = False

        # Must not raise and must not import otel_setup.
        assert maybe_configure_otel(_Settings(), service_name="probe") is None
