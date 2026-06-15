from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, Query

from examples.blog.author.domain.services.author_service import AuthorService
from examples.blog.author.infrastructure.di.author_container import AuthorContainer
from examples.blog.author.interface.server.schemas.author_schema import (
    AuthorResponse,
    CreateAuthorRequest,
    UpdateAuthorRequest,
)
from src._core.application.dtos.base_response import SuccessResponse

router = APIRouter()


@router.post(
    "/author",
    summary="Create author",
    response_model=SuccessResponse[AuthorResponse],
    response_model_exclude={"pagination"},
)
@inject
async def create_author(
    item: CreateAuthorRequest,
    author_service: AuthorService = Depends(Provide[AuthorContainer.author_service]),
) -> SuccessResponse[AuthorResponse]:
    data = await author_service.create_data(entity=item)
    return SuccessResponse(data=AuthorResponse(**data.model_dump()))


@router.get(
    "/authors",
    summary="List authors",
    response_model=SuccessResponse[list[AuthorResponse]],
)
@inject
async def list_authors(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, alias="pageSize", ge=1, le=100),
    author_service: AuthorService = Depends(Provide[AuthorContainer.author_service]),
) -> SuccessResponse[list[AuthorResponse]]:
    datas, pagination = await author_service.get_datas(page=page, page_size=page_size)
    return SuccessResponse(
        data=[AuthorResponse(**d.model_dump()) for d in datas],
        pagination=pagination,
    )


@router.get(
    "/author/{author_id}",
    summary="Get author",
    response_model=SuccessResponse[AuthorResponse],
    response_model_exclude={"pagination"},
)
@inject
async def get_author(
    author_id: int,
    author_service: AuthorService = Depends(Provide[AuthorContainer.author_service]),
) -> SuccessResponse[AuthorResponse]:
    data = await author_service.get_data_by_data_id(data_id=author_id)
    return SuccessResponse(data=AuthorResponse(**data.model_dump()))


@router.put(
    "/author/{author_id}",
    summary="Update author",
    response_model=SuccessResponse[AuthorResponse],
    response_model_exclude={"pagination"},
)
@inject
async def update_author(
    author_id: int,
    item: UpdateAuthorRequest,
    author_service: AuthorService = Depends(Provide[AuthorContainer.author_service]),
) -> SuccessResponse[AuthorResponse]:
    data = await author_service.update_data_by_data_id(data_id=author_id, entity=item)
    return SuccessResponse(data=AuthorResponse(**data.model_dump()))


@router.delete(
    "/author/{author_id}",
    summary="Delete author",
    response_model=SuccessResponse,
    response_model_exclude={"data", "pagination"},
)
@inject
async def delete_author(
    author_id: int,
    author_service: AuthorService = Depends(Provide[AuthorContainer.author_service]),
) -> SuccessResponse:
    success = await author_service.delete_data_by_data_id(data_id=author_id)
    return SuccessResponse(success=success)
