"""What is actually wired up in this deployment (#368).

The one thing that is **not** zero on a fresh install. Every count on the admin
dashboard starts at 0, but which optional infrastructure is live — and which is
silently running a stub — has a real answer on day one, and it is the answer a
new adopter needs first. Read-only over ``settings``; no database access, so it
cannot fail a page render.

Security contract
-----------------
Several of the enable/disable predicates in ``core_container`` key off
**credentials** (``dynamodb_access_key``, ``s3vectors_access_key``,
``notification_webhook_url``). This module reports only the *boolean result* of
those checks plus a non-secret type/provider label. That is enforced
mechanically rather than by review judgement: every value rendered must come
from a settings field on :data:`_SAFE_DETAIL_FIELDS`, and no field whose name
matches :data:`_SECRET_NAME_PARTS` may ever be read for display. See
``test_operational_status.py``, which asserts that credential-shaped settings
values never appear in the output.

Selector predicates are duplicated here on purpose — deliberately, not by
accident. Importing ``core_container`` would pull the DI graph (and its lazy
infra imports) into a page render, and the container resolves providers rather
than answering "is this on?". The predicates are one-liners; the cost of the
duplication is a comment pointing at the canonical source, and the tests below
pin the pairing so a change there fails here.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from src._core.config import settings

# Settings fields whose values may be rendered. Anything not listed is reported
# as a state only. Keep this list conservative: a field is safe when its value
# is a *type or provider name*, never a credential, endpoint or connection
# string.
_SAFE_DETAIL_FIELDS: frozenset[str] = frozenset(
    {
        "database_engine",
        "broker_type",
        "vector_store_type",
        "storage_type",
        "embedding_provider",
        "embedding_model_name",
        "llm_provider",
        "llm_model_name",
        "notification_provider",
    }
)

# Substrings that mark a settings field as credential-shaped. Used by the tests
# to prove no such value reaches the output.
_SECRET_NAME_PARTS: frozenset[str] = frozenset(
    {"key", "secret", "password", "token", "url", "dsn"}
)


class InfraState(StrEnum):
    """Why the three states are distinct rather than a bool.

    ADR 042 gives optional infrastructure two different disabled behaviours, and
    conflating them hides the one that bites: ``STUB`` means requests are served
    by a stand-in (``StubEmbedder``, PydanticAI ``TestModel``,
    ``NoopNotificationClient``) and therefore *appear to work* while doing
    nothing real. ``DISABLED`` means the capability is simply absent. An
    operator debugging "why are my embeddings meaningless" needs to see STUB.
    """

    ACTIVE = "active"
    STUB = "stub"
    DISABLED = "disabled"


@dataclass(frozen=True)
class InfraStatus:
    label: str
    state: InfraState
    detail: str | None = None


def _detail(field: str) -> str | None:
    """Read a display value, refusing anything not explicitly allowlisted."""
    if field not in _SAFE_DETAIL_FIELDS:
        raise ValueError(
            f"{field!r} is not an allowlisted display field; "
            "add it to _SAFE_DETAIL_FIELDS only if its value is not a credential"
        )
    value = getattr(settings, field, None)
    return str(value) if value else None


def collect_operational_status() -> list[InfraStatus]:
    """Current infra wiring, in the order an operator cares about.

    Predicate sources (canonical: ``_core/infrastructure/di/core_container.py``):
    storage → ``storage_type``, dynamodb → ``dynamodb_access_key``,
    s3vectors → ``s3vectors_access_key``, embedding → ``embedding_model_name``,
    llm → ``llm_model_name``, notification → ``notification_webhook_url``.
    """
    return [
        InfraStatus("Database", InfraState.ACTIVE, _detail("database_engine")),
        # Unset means the in-process broker, which runs tasks inline in the
        # producer — not "no broker" (#324).
        InfraStatus(
            "Broker",
            InfraState.ACTIVE,
            _detail("broker_type") or "inmemory",
        ),
        InfraStatus(
            "Vector store",
            InfraState.ACTIVE,
            _detail("vector_store_type") or "inmemory",
        ),
        InfraStatus(
            "Embedding",
            InfraState.ACTIVE if settings.embedding_model_name else InfraState.STUB,
            _detail("embedding_provider"),
        ),
        InfraStatus(
            "LLM",
            InfraState.ACTIVE if settings.llm_model_name else InfraState.STUB,
            _detail("llm_provider"),
        ),
        InfraStatus(
            "Error notification",
            InfraState.ACTIVE if settings.notification_webhook_url else InfraState.STUB,
            _detail("notification_provider"),
        ),
        InfraStatus(
            "Object storage",
            InfraState.ACTIVE if settings.storage_type else InfraState.DISABLED,
            _detail("storage_type"),
        ),
        InfraStatus(
            "DynamoDB",
            InfraState.ACTIVE if settings.dynamodb_access_key else InfraState.DISABLED,
            None,  # nothing safe to show: the predicate is the access key itself
        ),
        InfraStatus(
            "S3 Vectors",
            InfraState.ACTIVE if settings.s3vectors_access_key else InfraState.DISABLED,
            None,  # same
        ),
        InfraStatus(
            "OpenTelemetry",
            InfraState.ACTIVE if settings.otel_enabled else InfraState.DISABLED,
            None,
        ),
    ]
