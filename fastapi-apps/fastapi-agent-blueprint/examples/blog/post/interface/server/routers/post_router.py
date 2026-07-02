from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, Query

from src._core.application.dtos.base_response import SuccessResponse

from ....domain.services.post_service import PostService
from ....infrastructure.di.post_container import PostContainer
from ..schemas.post_schema import (
    CreatePostRequest,
    PostResponse,
    UpdatePostRequest,
)

router = APIRouter()


@router.post(
    "/post",
    summary="Create post",
    response_model=SuccessResponse[PostResponse],
    response_model_exclude={"pagination"},
)
@inject
async def create_post(
    item: CreatePostRequest,
    post_service: PostService = Depends(Provide[PostContainer.post_service]),
) -> SuccessResponse[PostResponse]:
    data = await post_service.create_data(entity=item)
    author_name = await post_service.get_author_display_name(data.author_id)
    return SuccessResponse(
        data=PostResponse(**data.model_dump(), author_display_name=author_name)
    )


@router.get(
    "/posts",
    summary="List posts",
    response_model=SuccessResponse[list[PostResponse]],
)
@inject
async def list_posts(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, alias="pageSize", ge=1, le=100),
    post_service: PostService = Depends(Provide[PostContainer.post_service]),
) -> SuccessResponse[list[PostResponse]]:
    datas, pagination = await post_service.get_datas(page=page, page_size=page_size)
    name_map = await post_service.get_author_display_names([d.author_id for d in datas])
    responses = [
        PostResponse(
            **d.model_dump(),
            author_display_name=name_map.get(d.author_id, "Unknown"),
        )
        for d in datas
    ]
    return SuccessResponse(data=responses, pagination=pagination)


@router.get(
    "/post/{post_id}",
    summary="Get post",
    response_model=SuccessResponse[PostResponse],
    response_model_exclude={"pagination"},
)
@inject
async def get_post(
    post_id: int,
    post_service: PostService = Depends(Provide[PostContainer.post_service]),
) -> SuccessResponse[PostResponse]:
    data = await post_service.get_data_by_data_id(data_id=post_id)
    author_name = await post_service.get_author_display_name(data.author_id)
    return SuccessResponse(
        data=PostResponse(**data.model_dump(), author_display_name=author_name)
    )


@router.put(
    "/post/{post_id}",
    summary="Update post",
    response_model=SuccessResponse[PostResponse],
    response_model_exclude={"pagination"},
)
@inject
async def update_post(
    post_id: int,
    item: UpdatePostRequest,
    post_service: PostService = Depends(Provide[PostContainer.post_service]),
) -> SuccessResponse[PostResponse]:
    data = await post_service.update_data_by_data_id(data_id=post_id, entity=item)
    author_name = await post_service.get_author_display_name(data.author_id)
    return SuccessResponse(
        data=PostResponse(**data.model_dump(), author_display_name=author_name)
    )


@router.delete(
    "/post/{post_id}",
    summary="Delete post",
    response_model=SuccessResponse,
    response_model_exclude={"data", "pagination"},
)
@inject
async def delete_post(
    post_id: int,
    post_service: PostService = Depends(Provide[PostContainer.post_service]),
) -> SuccessResponse:
    success = await post_service.delete_data_by_data_id(data_id=post_id)
    return SuccessResponse(success=success)
