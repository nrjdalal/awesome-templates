from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

import structlog
from pydantic import BaseModel
from sqlalchemy import Select, func, select
from sqlalchemy.exc import IntegrityError

from src._core.infrastructure.persistence.rdb.base_repository import BaseRepository
from src._core.infrastructure.persistence.rdb.database import Database
from src.ai_usage.domain.dtos.ai_usage_dto import (
    AiUsageByOrgDTO,
    AiUsageDTO,
    AiUsageSummaryDTO,
)
from src.ai_usage.domain.exceptions.ai_usage_exceptions import (
    AiUsageImmutableException,
)
from src.ai_usage.infrastructure.database.models.ai_usage_model import AiUsageModel
from src.ai_usage.interface.server.schemas.ai_usage_schema import CreateAiUsageRequest

_logger = structlog.stdlib.get_logger("src.ai_usage.infrastructure.repositories")


class AiUsageRepository(BaseRepository[AiUsageDTO]):
    def __init__(self, database: Database) -> None:
        super().__init__(
            database=database,
            model=AiUsageModel,
            return_entity=AiUsageDTO,
        )
        # In-process serialization keeps SQLite-based tests stable. The DB
        # unique constraint remains the correctness boundary across processes.
        self._insert_lock = asyncio.Lock()

    async def insert_usage_once(self, entity: CreateAiUsageRequest) -> AiUsageDTO:
        async with self._insert_lock:
            return await self._insert_usage_once(entity)

    async def _insert_usage_once(self, entity: CreateAiUsageRequest) -> AiUsageDTO:
        async with self.database.async_session_factory() as session:
            data = AiUsageModel(**entity.model_dump(exclude_none=True))
            session.add(data)
            try:
                await session.commit()
                await session.refresh(data)
            except IntegrityError:
                await session.rollback()
                existing = await self._select_existing_by_call_id(entity.call_id)
                if existing is None:
                    raise
                differing_fields = _differing_usage_fields(entity, existing)
                if differing_fields:
                    _logger.warning(
                        "ai_usage_idempotent_collision",
                        call_id=entity.call_id,
                        differing_fields=differing_fields,
                    )
                else:
                    _logger.info(
                        "ai_usage_idempotent_replay",
                        call_id=entity.call_id,
                    )
                return existing
            return AiUsageDTO.model_validate(data, from_attributes=True)

    async def _select_existing_by_call_id(self, call_id: str) -> AiUsageDTO | None:
        for attempt in range(3):
            async with self.database.async_session_factory() as session:
                result = await session.execute(
                    select(AiUsageModel).where(AiUsageModel.call_id == call_id)
                )
                existing = result.scalar_one_or_none()
                if existing is not None:
                    return AiUsageDTO.model_validate(existing, from_attributes=True)
            _logger.warning(
                "ai_usage_call_id_lookup_retry",
                call_id=call_id,
                attempt=attempt + 1,
            )
            await asyncio.sleep(0.01 * (attempt + 1))
        return None

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
    ) -> tuple[list[AiUsageDTO], int]:
        async with self.database.session() as session:
            query = _apply_filters(
                select(AiUsageModel),
                org_id=org_id,
                agent_name=agent_name,
                model=model,
                status=status,
                start_at=start_at,
                end_at=end_at,
            ).order_by(AiUsageModel.occurred_at.desc(), AiUsageModel.id.desc())
            count_query = _apply_filters(
                select(func.count()).select_from(AiUsageModel),
                org_id=org_id,
                agent_name=agent_name,
                model=model,
                status=status,
                start_at=start_at,
                end_at=end_at,
            )

            result = await session.execute(
                query.offset((page - 1) * page_size).limit(page_size)
            )
            datas = result.scalars().all()
            count_result = await session.execute(count_query)
            total_count = count_result.scalar_one()
            return [
                AiUsageDTO.model_validate(data, from_attributes=True) for data in datas
            ], total_count

    async def select_usage_summary(
        self,
        *,
        org_id: str | None = None,
        agent_name: str | None = None,
        model: str | None = None,
        status: str | None = None,
        start_at: datetime | None = None,
        end_at: datetime | None = None,
    ) -> AiUsageSummaryDTO:
        async with self.database.session() as session:
            query = _apply_filters(
                _summary_select(),
                org_id=org_id,
                agent_name=agent_name,
                model=model,
                status=status,
                start_at=start_at,
                end_at=end_at,
            )
            result = await session.execute(query)
            row = result.one()
            return _summary_from_row(row._mapping)

    async def select_usage_by_org(
        self,
        *,
        org_id: str | None = None,
        agent_name: str | None = None,
        model: str | None = None,
        status: str | None = None,
        start_at: datetime | None = None,
        end_at: datetime | None = None,
    ) -> list[AiUsageByOrgDTO]:
        async with self.database.session() as session:
            query = _apply_filters(
                select(AiUsageModel.org_id, *_summary_columns()).group_by(
                    AiUsageModel.org_id
                ),
                org_id=org_id,
                agent_name=agent_name,
                model=model,
                status=status,
                start_at=start_at,
                end_at=end_at,
            ).order_by(AiUsageModel.org_id.asc())
            result = await session.execute(query)
            return [
                AiUsageByOrgDTO(
                    org_id=row._mapping["org_id"],
                    **_summary_from_row(row._mapping).model_dump(),
                )
                for row in result.all()
            ]

    async def update_data_by_data_id(
        self, data_id: int, entity: BaseModel
    ) -> AiUsageDTO:
        raise AiUsageImmutableException()

    async def delete_data_by_data_id(self, data_id: int) -> bool:
        raise AiUsageImmutableException()


def _apply_filters(
    query: Select[Any],
    *,
    org_id: str | None,
    agent_name: str | None,
    model: str | None,
    status: str | None,
    start_at: datetime | None,
    end_at: datetime | None,
) -> Select[Any]:
    if org_id is not None:
        query = query.where(AiUsageModel.org_id == org_id)
    if agent_name is not None:
        query = query.where(AiUsageModel.agent_name == agent_name)
    if model is not None:
        query = query.where(AiUsageModel.model == model)
    if status is not None:
        query = query.where(AiUsageModel.status == status)
    if start_at is not None:
        query = query.where(AiUsageModel.occurred_at >= start_at)
    if end_at is not None:
        query = query.where(AiUsageModel.occurred_at <= end_at)
    return query


def _differing_usage_fields(
    entity: CreateAiUsageRequest, existing: AiUsageDTO
) -> list[str]:
    entity_data = entity.model_dump(exclude={"usage_metadata"})
    existing_data = existing.model_dump(include=set(entity_data))
    return [
        field_name
        for field_name, entity_value in entity_data.items()
        if existing_data.get(field_name) != entity_value
    ]


def _summary_columns():
    return (
        func.count(AiUsageModel.id).label("call_count"),
        func.coalesce(func.sum(AiUsageModel.requests), 0).label("request_count"),
        func.coalesce(func.sum(AiUsageModel.input_tokens), 0).label("input_tokens"),
        func.coalesce(func.sum(AiUsageModel.output_tokens), 0).label("output_tokens"),
        func.coalesce(func.sum(AiUsageModel.cache_read_tokens), 0).label(
            "cache_read_tokens"
        ),
        func.coalesce(func.sum(AiUsageModel.cache_write_tokens), 0).label(
            "cache_write_tokens"
        ),
        func.coalesce(func.sum(AiUsageModel.reasoning_tokens), 0).label(
            "reasoning_tokens"
        ),
        func.coalesce(func.sum(AiUsageModel.total_tokens), 0).label("total_tokens"),
    )


def _summary_select() -> Select[Any]:
    return select(*_summary_columns())


def _summary_from_row(row: Any) -> AiUsageSummaryDTO:
    return AiUsageSummaryDTO(
        call_count=int(row["call_count"] or 0),
        request_count=int(row["request_count"] or 0),
        input_tokens=int(row["input_tokens"] or 0),
        output_tokens=int(row["output_tokens"] or 0),
        cache_read_tokens=int(row["cache_read_tokens"] or 0),
        cache_write_tokens=int(row["cache_write_tokens"] or 0),
        reasoning_tokens=int(row["reasoning_tokens"] or 0),
        total_tokens=int(row["total_tokens"] or 0),
    )
