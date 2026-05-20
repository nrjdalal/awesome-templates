from decimal import Decimal

import pytest
from pydantic import ValidationError

from src._core.domain.value_objects.agent_usage_record import AgentUsageRecord
from src._core.domain.value_objects.prompt_snapshot import PromptSnapshot


def test_agent_usage_record_uppercases_provider_cost_currency():
    record = AgentUsageRecord(
        call_id="call-1",
        agent_name="classifier",
        model="gpt-test",
        provider_cost_amount=Decimal("0.001"),
        provider_cost_currency="usd",
        provider_cost_source="response",
    )

    assert record.provider_cost_currency == "USD"


def test_agent_usage_record_requires_provider_cost_fields_together():
    with pytest.raises(ValidationError, match="provider cost"):
        AgentUsageRecord(
            call_id="call-1",
            agent_name="classifier",
            model="gpt-test",
            provider_cost_amount=Decimal("0.001"),
        )


def test_agent_usage_record_rejects_unknown_prompt_source():
    with pytest.raises(ValidationError):
        AgentUsageRecord(
            call_id="call-1",
            agent_name="classifier",
            model="gpt-test",
            prompt_source="database",
        )


def test_prompt_snapshot_validates_name_and_source():
    snapshot = PromptSnapshot(
        name="classify-system",
        content="Classify the text.",
        source="inline",
        version="v1",
    )

    assert snapshot.name == "classify-system"
    assert snapshot.source == "inline"


def test_prompt_snapshot_rejects_empty_name():
    with pytest.raises(ValidationError):
        PromptSnapshot(name="", content="Prompt", source="inline")
