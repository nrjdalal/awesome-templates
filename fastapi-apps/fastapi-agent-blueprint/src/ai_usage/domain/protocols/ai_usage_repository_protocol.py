from __future__ import annotations

from datetime import datetime
from typing import Protocol

from src._core.domain.protocols.repository_protocol import BaseRepositoryProtocol
from src.ai_usage.domain.dtos.ai_usage_dto import (
    AiUsageByOrgDTO,
    AiUsageDTO,
    AiUsageSummaryDTO,
)
from src.ai_usage.interface.server.schemas.ai_usage_schema import CreateAiUsageRequest


class AiUsageRepositoryProtocol(BaseRepositoryProtocol[AiUsageDTO], Protocol):
    async def insert_usage_once(self, entity: CreateAiUsageRequest) -> AiUsageDTO: ...

    async def select_usage_logs(
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
    ) -> tuple[list[AiUsageDTO], int]: ...

    async def select_usage_summary(
        self,
        *,
        org_id: str | None = None,
        agent_name: str | None = None,
        model: str | None = None,
        status: str | None = None,
        start_at: datetime | None = None,
        end_at: datetime | None = None,
    ) -> AiUsageSummaryDTO: ...

    async def select_usage_by_org(
        self,
        *,
        org_id: str | None = None,
        agent_name: str | None = None,
        model: str | None = None,
        status: str | None = None,
        start_at: datetime | None = None,
        end_at: datetime | None = None,
    ) -> list[AiUsageByOrgDTO]: ...
