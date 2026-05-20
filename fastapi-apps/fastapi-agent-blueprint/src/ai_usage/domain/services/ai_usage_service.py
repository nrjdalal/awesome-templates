from __future__ import annotations

from datetime import datetime

from src._core.domain.services.base_service import BaseService
from src._core.domain.value_objects.agent_usage_record import AgentUsageRecord
from src.ai_usage.domain.dtos.ai_usage_dto import (
    AiUsageByOrgDTO,
    AiUsageDTO,
    AiUsageSummaryDTO,
)
from src.ai_usage.domain.exceptions.ai_usage_exceptions import (
    AiUsageImmutableException,
)
from src.ai_usage.domain.protocols.ai_usage_repository_protocol import (
    AiUsageRepositoryProtocol,
)
from src.ai_usage.interface.server.schemas.ai_usage_schema import CreateAiUsageRequest


class AiUsageService(
    BaseService[CreateAiUsageRequest, CreateAiUsageRequest, AiUsageDTO]
):
    def __init__(self, ai_usage_repository: AiUsageRepositoryProtocol) -> None:
        super().__init__(repository=ai_usage_repository)
        self._ai_usage_repository = ai_usage_repository

    async def record_usage(self, record: AgentUsageRecord) -> AgentUsageRecord:
        await self.record_usage_data(record)
        return record

    async def record_usage_data(self, record: AgentUsageRecord) -> AiUsageDTO:
        request = CreateAiUsageRequest(**record.model_dump())
        return await self._ai_usage_repository.insert_usage_once(entity=request)

    async def get_usage_logs(
        self,
        *,
        page: int,
        page_size: int,
        org_id: str | None = None,
        agent_name: str | None = None,
        model: str | None = None,
        status: str | None = None,
        start_at: datetime | None = None,
        end_at: datetime | None = None,
    ) -> tuple[list[AiUsageDTO], int]:
        return await self._ai_usage_repository.select_usage_logs(
            page=page,
            page_size=page_size,
            org_id=org_id,
            agent_name=agent_name,
            model=model,
            status=status,
            start_at=start_at,
            end_at=end_at,
        )

    async def get_usage_summary(
        self,
        *,
        org_id: str | None = None,
        agent_name: str | None = None,
        model: str | None = None,
        status: str | None = None,
        start_at: datetime | None = None,
        end_at: datetime | None = None,
    ) -> tuple[AiUsageSummaryDTO, list[AiUsageByOrgDTO]]:
        summary = await self._ai_usage_repository.select_usage_summary(
            org_id=org_id,
            agent_name=agent_name,
            model=model,
            status=status,
            start_at=start_at,
            end_at=end_at,
        )
        by_org = await self._ai_usage_repository.select_usage_by_org(
            org_id=org_id,
            agent_name=agent_name,
            model=model,
            status=status,
            start_at=start_at,
            end_at=end_at,
        )
        return summary, by_org

    async def update_data_by_data_id(
        self, data_id: int, entity: CreateAiUsageRequest
    ) -> AiUsageDTO:
        raise AiUsageImmutableException()

    async def delete_data_by_data_id(self, data_id: int) -> bool:
        raise AiUsageImmutableException()
