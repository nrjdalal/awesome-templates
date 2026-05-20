from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from src.ai_usage.infrastructure.repositories.ai_usage_repository import (
    AiUsageRepository,
)
from tests.factories.ai_usage_factory import make_create_ai_usage_request


@pytest.mark.asyncio
async def test_insert_usage_once_returns_existing_for_duplicate_call_id(test_db):
    repo = AiUsageRepository(database=test_db)
    request = make_create_ai_usage_request(call_id="dup-call")

    first = await repo.insert_usage_once(entity=request)
    second = await repo.insert_usage_once(entity=request)

    assert first.id == second.id


@pytest.mark.asyncio
async def test_insert_usage_once_handles_concurrent_duplicate_call_id(test_db):
    repo = AiUsageRepository(database=test_db)
    request = make_create_ai_usage_request(call_id="race-call")

    results = await asyncio.gather(
        repo.insert_usage_once(entity=request),
        repo.insert_usage_once(entity=request),
    )

    assert results[0].id == results[1].id


@pytest.mark.asyncio
async def test_select_usage_logs_filters_and_counts(test_db):
    repo = AiUsageRepository(database=test_db)
    await repo.insert_usage_once(
        entity=make_create_ai_usage_request(
            call_id="org-1-call",
            org_id="filter-org-1",
            model="gpt-a",
        )
    )
    await repo.insert_usage_once(
        entity=make_create_ai_usage_request(
            call_id="org-2-call",
            org_id="filter-org-2",
            model="gpt-b",
        )
    )

    datas, total = await repo.select_usage_logs(
        page=1, page_size=10, org_id="filter-org-1"
    )

    assert total == 1
    assert datas[0].call_id == "org-1-call"


@pytest.mark.asyncio
async def test_select_usage_summary_and_by_org(test_db):
    repo = AiUsageRepository(database=test_db)
    now = datetime.now(UTC).replace(tzinfo=None)
    await repo.insert_usage_once(
        entity=make_create_ai_usage_request(
            call_id="summary-1",
            org_id="summary-org",
            occurred_at=now - timedelta(minutes=1),
        )
    )
    await repo.insert_usage_once(
        entity=make_create_ai_usage_request(
            call_id="summary-2",
            org_id="summary-org",
            occurred_at=now,
        )
    )

    summary = await repo.select_usage_summary(org_id="summary-org")
    by_org = await repo.select_usage_by_org(org_id="summary-org")

    assert summary.call_count == 2
    assert summary.total_tokens == 42
    assert by_org[0].org_id == "summary-org"
    assert by_org[0].total_tokens == 42


@pytest.mark.asyncio
async def test_provider_cost_snapshot_round_trips(test_db):
    repo = AiUsageRepository(database=test_db)
    request = make_create_ai_usage_request(
        call_id="cost-call",
        provider_cost_amount=Decimal("0.0000123456"),
        provider_cost_currency="usd",
        provider_cost_source="response",
    )

    created = await repo.insert_usage_once(entity=request)

    assert created.provider_cost_amount == Decimal("0.0000123456")
    assert created.provider_cost_currency == "USD"
    assert created.provider_cost_source == "response"
