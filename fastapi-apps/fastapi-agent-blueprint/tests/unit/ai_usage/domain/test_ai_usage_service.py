from __future__ import annotations

import pytest

from src.ai_usage.domain.dtos.ai_usage_dto import (
    AiUsageByOrgDTO,
    AiUsageSummaryDTO,
)
from src.ai_usage.domain.exceptions.ai_usage_exceptions import (
    AiUsageImmutableException,
)
from src.ai_usage.domain.services.ai_usage_service import AiUsageService
from tests.factories.ai_usage_factory import (
    make_agent_usage_record,
    make_ai_usage_dto,
    make_create_ai_usage_request,
)


class MockAiUsageRepository:
    def __init__(self) -> None:
        self.inserted = []

    async def insert_usage_once(self, entity):
        self.inserted.append(entity)
        return make_ai_usage_dto(call_id=entity.call_id)

    async def select_usage_logs(self, **kwargs):
        return [make_ai_usage_dto()], 1

    async def select_usage_summary(self, **kwargs):
        return AiUsageSummaryDTO(
            call_count=1,
            request_count=1,
            input_tokens=10,
            output_tokens=5,
            cache_read_tokens=2,
            cache_write_tokens=1,
            reasoning_tokens=3,
            total_tokens=21,
        )

    async def select_usage_by_org(self, **kwargs):
        return [
            AiUsageByOrgDTO(
                org_id="org-1",
                call_count=1,
                request_count=1,
                input_tokens=10,
                output_tokens=5,
                cache_read_tokens=2,
                cache_write_tokens=1,
                reasoning_tokens=3,
                total_tokens=21,
            )
        ]


@pytest.mark.asyncio
async def test_record_usage_converts_record_to_request():
    repo = MockAiUsageRepository()
    service = AiUsageService(ai_usage_repository=repo)

    record = make_agent_usage_record(call_id="call-1")
    returned = await service.record_usage(record)

    assert returned == record
    assert repo.inserted[0].call_id == "call-1"
    assert repo.inserted[0].total_tokens == 21


@pytest.mark.asyncio
async def test_get_usage_summary_delegates_to_repository():
    service = AiUsageService(ai_usage_repository=MockAiUsageRepository())

    summary, by_org = await service.get_usage_summary(org_id="org-1")

    assert summary.total_tokens == 21
    assert by_org[0].org_id == "org-1"


@pytest.mark.asyncio
async def test_update_is_rejected_for_append_only_usage():
    service = AiUsageService(ai_usage_repository=MockAiUsageRepository())

    with pytest.raises(AiUsageImmutableException):
        await service.update_data_by_data_id(
            data_id=1,
            entity=make_create_ai_usage_request(),
        )


@pytest.mark.asyncio
async def test_delete_is_rejected_for_append_only_usage():
    service = AiUsageService(ai_usage_repository=MockAiUsageRepository())

    with pytest.raises(AiUsageImmutableException):
        await service.delete_data_by_data_id(data_id=1)
