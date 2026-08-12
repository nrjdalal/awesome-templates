"""The operational-status panel must never render a credential (#368).

The panel exists because "what is wired up" is the only non-zero information on a
fresh install. The hazard is that several of the enable/disable predicates in
``core_container`` key off **credentials** — ``dynamodb_access_key``,
``s3vectors_access_key``, ``notification_webhook_url`` — so the code that decides
what to display is reading secrets by construction. Showing a state derived from
a secret is fine; showing the secret is not.

These tests pin that mechanically rather than by review judgement: settings are
populated with sentinel values for every credential-shaped field, and the
rendered output is searched for them.
"""

from __future__ import annotations

import pytest

from src._apps.admin.operational_status import (
    _SAFE_DETAIL_FIELDS,
    _SECRET_NAME_PARTS,
    InfraState,
    _detail,
    collect_operational_status,
)
from src._core.config import settings

# Distinctive so a substring search cannot produce a false negative.
_SENTINEL = "SHOULD-NEVER-RENDER-b3f9a1"

# Real settings *fields*. `notification_webhook_url`, `embedding_model_name` and
# `llm_model_name` are computed properties with no setter, so the sentinel goes
# into the fields they derive from — which is also where a real secret lives.
_CREDENTIAL_FIELDS = (
    "dynamodb_access_key",
    "s3vectors_access_key",
    "slack_webhook_url",
    "discord_webhook_url",
    "embedding_openai_api_key",
    "llm_api_key",
)


@pytest.fixture
def everything_enabled(monkeypatch):
    """Turn every optional infra on, with credentials set to the sentinel.

    Enabling everything is the point: a disabled panel has nothing to leak.
    """
    for field in _CREDENTIAL_FIELDS:
        if hasattr(settings, field):
            monkeypatch.setattr(settings, field, _SENTINEL, raising=False)
    monkeypatch.setattr(settings, "storage_type", "s3", raising=False)
    monkeypatch.setattr(settings, "broker_type", "sqs", raising=False)
    monkeypatch.setattr(settings, "vector_store_type", "s3vectors", raising=False)
    # `embedding_model_name` / `llm_model_name` are derived from provider+model.
    monkeypatch.setattr(settings, "embedding_provider", "openai", raising=False)
    monkeypatch.setattr(
        settings, "embedding_model", "text-embedding-3-small", raising=False
    )
    monkeypatch.setattr(settings, "llm_provider", "openai", raising=False)
    monkeypatch.setattr(settings, "llm_model", "gpt-4o", raising=False)
    monkeypatch.setattr(settings, "notification_provider", "slack", raising=False)
    monkeypatch.setattr(settings, "otel_enabled", True, raising=False)
    return settings


class TestNoCredentialReachesTheOutput:
    def test_sentinel_credentials_are_absent_from_every_field(
        self, everything_enabled
    ) -> None:
        rendered = " | ".join(
            f"{row.label} {row.state} {row.detail or ''}"
            for row in collect_operational_status()
        )

        assert _SENTINEL not in rendered, (
            "a credential-shaped settings value reached the operational-status "
            f"panel: {rendered}"
        )

    def test_every_allowlisted_field_is_credential_free_by_name(self) -> None:
        """The allowlist is the enforcement point, so guard the allowlist itself.

        A future field added to `_SAFE_DETAIL_FIELDS` whose name looks like a
        credential fails here rather than silently rendering.
        """
        offenders = {
            field
            for field in _SAFE_DETAIL_FIELDS
            for part in _SECRET_NAME_PARTS
            if part in field
        }
        assert not offenders, f"credential-shaped names on the allowlist: {offenders}"

    def test_detail_refuses_a_field_outside_the_allowlist(self) -> None:
        with pytest.raises(ValueError, match="not an allowlisted display field"):
            _detail("notification_webhook_url")

    def test_dynamodb_and_s3vectors_show_no_detail_at_all(
        self, everything_enabled
    ) -> None:
        """Their predicate *is* the access key, so there is nothing safe to show."""
        rows = {row.label: row for row in collect_operational_status()}

        assert rows["DynamoDB"].detail is None
        assert rows["S3 Vectors"].detail is None
        assert rows["DynamoDB"].state is InfraState.ACTIVE  # enabled, still no detail


class TestStateSemantics:
    def test_stub_and_disabled_are_not_conflated(self, monkeypatch) -> None:
        """ADR 042 gives two different disabled behaviours and the distinction is
        the useful part: STUB serves requests with a stand-in and therefore looks
        like it works."""
        # Clear the *fields*; the model-name and webhook-url properties follow.
        for field in (
            "embedding_provider",
            "embedding_model",
            "llm_provider",
            "llm_model",
            "notification_provider",
            "slack_webhook_url",
            "discord_webhook_url",
            "storage_type",
            "dynamodb_access_key",
            "s3vectors_access_key",
        ):
            monkeypatch.setattr(settings, field, None, raising=False)
        monkeypatch.setattr(settings, "otel_enabled", False, raising=False)

        rows = {row.label: row.state for row in collect_operational_status()}

        assert rows["Embedding"] is InfraState.STUB
        assert rows["LLM"] is InfraState.STUB
        assert rows["Error notification"] is InfraState.STUB
        assert rows["Object storage"] is InfraState.DISABLED
        assert rows["DynamoDB"] is InfraState.DISABLED
        assert rows["OpenTelemetry"] is InfraState.DISABLED

    def test_unset_broker_and_vector_store_report_inmemory_not_absent(
        self, monkeypatch
    ) -> None:
        """`BROKER_TYPE` unset means the in-process broker that runs tasks inline
        in the producer (#324) — reporting it as "off" would be wrong."""
        monkeypatch.setattr(settings, "broker_type", None, raising=False)
        monkeypatch.setattr(settings, "vector_store_type", None, raising=False)

        rows = {row.label: row for row in collect_operational_status()}

        assert rows["Broker"].detail == "inmemory"
        assert rows["Broker"].state is InfraState.ACTIVE
        assert rows["Vector store"].detail == "inmemory"


class TestPredicateParityWithTheContainer:
    """The panel duplicates the container's selector predicates, so pin the pair.

    Duplication is deliberate — importing the DI graph into a page render to ask
    "is this on?" is the wrong dependency — but a silent divergence would make
    the panel lie. These compare the panel's verdict against the container's own
    selector functions under the same settings.
    """

    @pytest.mark.parametrize(
        ("label", "selector_name"),
        [
            ("Embedding", "_embedding_selector"),
            ("LLM", "_llm_selector"),
            ("Error notification", "_notification_selector"),
            ("Object storage", "_storage_selector"),
            ("DynamoDB", "_dynamodb_selector"),
            ("S3 Vectors", "_s3vector_selector"),
        ],
    )
    def test_panel_agrees_with_selector(
        self, everything_enabled, label, selector_name
    ) -> None:
        from src._core.infrastructure.di import core_container

        selector = getattr(core_container, selector_name)
        rows = {row.label: row.state for row in collect_operational_status()}

        panel_says_on = rows[label] is InfraState.ACTIVE
        container_says_on = selector() == "enabled"
        assert panel_says_on == container_says_on, (
            f"{label}: panel={rows[label]} but {selector_name}()={selector()}"
        )
