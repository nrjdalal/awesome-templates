from typing import Annotated

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, Path

from src._core.application.dtos.base_response import SuccessResponse

from ....domain.services.link_service import LinkService
from ....infrastructure.di.url_shortener_container import UrlShortenerContainer
from ..schemas.link_schema import CreateLinkRequest, LinkResponse

router = APIRouter()


@router.post(
    "/link",
    summary="Create link",
    response_model=SuccessResponse[LinkResponse],
    response_model_exclude={"pagination"},
)
@inject
async def create_link(
    item: CreateLinkRequest,
    link_service: LinkService = Depends(Provide[UrlShortenerContainer.link_service]),
) -> SuccessResponse[LinkResponse]:
    data = await link_service.create_data(entity=item)
    return SuccessResponse(data=LinkResponse(**data.model_dump()))


@router.get(
    "/link/{short_code}",
    summary="Get link by short code",
    response_model=SuccessResponse[LinkResponse],
    response_model_exclude={"pagination"},
)
@inject
async def get_link(
    short_code: Annotated[str, Path(min_length=1, max_length=64)],
    link_service: LinkService = Depends(Provide[UrlShortenerContainer.link_service]),
) -> SuccessResponse[LinkResponse]:
    data = await link_service.get_by_short_code(short_code=short_code)
    return SuccessResponse(data=LinkResponse(**data.model_dump()))


@router.delete(
    "/link/{short_code}",
    summary="Delete link by short code",
    response_model=SuccessResponse,
    response_model_exclude={"data", "pagination"},
)
@inject
async def delete_link(
    short_code: Annotated[str, Path(min_length=1, max_length=64)],
    link_service: LinkService = Depends(Provide[UrlShortenerContainer.link_service]),
) -> SuccessResponse:
    success = await link_service.delete_by_short_code(short_code=short_code)
    return SuccessResponse(success=success)
