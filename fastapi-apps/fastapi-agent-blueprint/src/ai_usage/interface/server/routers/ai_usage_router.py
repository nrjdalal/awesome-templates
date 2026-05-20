from __future__ import annotations

from datetime import datetime

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, Query

from src._core.application.dtos.base_response import SuccessResponse
from src._core.common.pagination import make_pagination
from src.ai_usage.domain.services.ai_usage_service import AiUsageService
from src.ai_usage.infrastructure.di.ai_usage_container import AiUsageContainer
from src.ai_usage.interface.server.schemas.ai_usage_schema import (
    AiUsageByOrgResponse,
    AiUsageResponse,
    AiUsageSummaryResponse,
)

router = APIRouter()


@router.get(
    "/usage",
    summary="List AI usage logs",
    response_model=SuccessResponse[list[AiUsageResponse]],
)
@inject
async def list_usage_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, alias="pageSize", ge=1, le=100),
    org_id: str | None = Query(default=None, alias="orgId", max_length=64),
    agent_name: str | None = Query(default=None, alias="agentName", max_length=100),
    model: str | None = Query(default=None, max_length=200),
    status: str | None = Query(default=None, max_length=20),
    start_at: datetime | None = Query(default=None, alias="startAt"),
    end_at: datetime | None = Query(default=None, alias="endAt"),
    ai_usage_service: AiUsageService = Depends(
        Provide[AiUsageContainer.ai_usage_service]
    ),
) -> SuccessResponse[list[AiUsageResponse]]:
    datas, total_count = await ai_usage_service.get_usage_logs(
        page=page,
        page_size=page_size,
        org_id=org_id,
        agent_name=agent_name,
        model=model,
        status=status,
        start_at=start_at,
        end_at=end_at,
    )
    pagination = make_pagination(
        total_items=total_count, page=page, page_size=page_size
    )
    return SuccessResponse(
        data=[AiUsageResponse(**data.model_dump()) for data in datas],
        pagination=pagination,
    )


@router.get(
    "/usage/summary",
    summary="Summarize AI usage logs",
    response_model=SuccessResponse[AiUsageSummaryResponse],
    response_model_exclude={"pagination"},
)
@inject
async def summarize_usage_logs(
    org_id: str | None = Query(default=None, alias="orgId", max_length=64),
    agent_name: str | None = Query(default=None, alias="agentName", max_length=100),
    model: str | None = Query(default=None, max_length=200),
    status: str | None = Query(default=None, max_length=20),
    start_at: datetime | None = Query(default=None, alias="startAt"),
    end_at: datetime | None = Query(default=None, alias="endAt"),
    ai_usage_service: AiUsageService = Depends(
        Provide[AiUsageContainer.ai_usage_service]
    ),
) -> SuccessResponse[AiUsageSummaryResponse]:
    summary, by_org = await ai_usage_service.get_usage_summary(
        org_id=org_id,
        agent_name=agent_name,
        model=model,
        status=status,
        start_at=start_at,
        end_at=end_at,
    )
    return SuccessResponse(
        data=AiUsageSummaryResponse(
            **summary.model_dump(),
            by_org=[AiUsageByOrgResponse(**item.model_dump()) for item in by_org],
        )
    )


@router.get(
    "/usage/{usage_id}",
    summary="Get AI usage log by ID",
    response_model=SuccessResponse[AiUsageResponse],
    response_model_exclude={"pagination"},
)
@inject
async def get_usage_log(
    usage_id: int,
    ai_usage_service: AiUsageService = Depends(
        Provide[AiUsageContainer.ai_usage_service]
    ),
) -> SuccessResponse[AiUsageResponse]:
    data = await ai_usage_service.get_data_by_data_id(data_id=usage_id)
    return SuccessResponse(data=AiUsageResponse(**data.model_dump()))
