from typing import Annotated

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, Query
from pydantic import Field

from src._core.application.dtos.base_response import SuccessResponse
from src.admin_identity.interface.server.dependencies.admin_auth_dependencies import (
    require_admin,
)
from src.user.domain.services.user_service import UserService
from src.user.infrastructure.di.user_container import UserContainer
from src.user.interface.server.schemas.user_schema import (
    CreateUserRequest,
    UpdateUserRequest,
    UserResponse,
)

# All /v1/user routes are admin-only (#199): user management (read + CUD)
# exposes other users' PII. Self-service profile reads use /v1/auth/me.
# New routes added to this router inherit the admin gate by default (default-deny).
router = APIRouter(dependencies=[Depends(require_admin)])

# Collection bounds (#322). Batch create is the sharp one: every element costs a
# bcrypt round (~220 ms), so an unbounded list is one request holding a worker
# thread for N x that. Bounding at the schema layer rejects it with a 422 before
# any hashing starts. by-ids is bounded for the same reason a page size is —
# it expands straight into an IN (...) clause.
MAX_BATCH_SIZE = 100
MAX_IDS_PER_QUERY = 100


# ==========================================================================================


@router.post(
    "/user",
    summary="Create user",
    response_model=SuccessResponse[UserResponse],
    response_model_exclude={"pagination"},
)
@inject
async def create_user(
    item: CreateUserRequest,
    user_service: UserService = Depends(Provide[UserContainer.user_service]),
) -> SuccessResponse[UserResponse]:
    data = await user_service.create_data(entity=item)
    return SuccessResponse(data=UserResponse(**data.model_dump(exclude={"password"})))


# ==========================================================================================


@router.post(
    "/users",
    summary="Create users (batch)",
    response_model=SuccessResponse[list[UserResponse]],
    response_model_exclude={"pagination"},
)
@inject
async def create_users(
    items: Annotated[list[CreateUserRequest], Field(max_length=MAX_BATCH_SIZE)],
    user_service: UserService = Depends(Provide[UserContainer.user_service]),
) -> SuccessResponse[list[UserResponse]]:
    datas = await user_service.create_datas(entities=items)
    return SuccessResponse(
        data=[UserResponse(**data.model_dump(exclude={"password"})) for data in datas]
    )


# ==========================================================================================


@router.get(
    "/users",
    summary="List all users",
    response_model=SuccessResponse[list[UserResponse]],
)
@inject
async def get_user(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, alias="pageSize", ge=1, le=100),
    user_service: UserService = Depends(Provide[UserContainer.user_service]),
) -> SuccessResponse[list[UserResponse]]:
    datas, pagination = await user_service.get_datas(page=page, page_size=page_size)
    return SuccessResponse(
        data=[UserResponse(**data.model_dump(exclude={"password"})) for data in datas],
        pagination=pagination,
    )


# ==========================================================================================


@router.get(
    "/user/by-ids",
    summary="Get users by IDs",
    response_model=SuccessResponse[list[UserResponse]],
    response_model_exclude={"pagination"},
)
@inject
async def get_user_by_ids(
    ids: list[int] = Query(
        ...,
        description="Comma-separated list of IDs (e.g., 0,1,2)",
        max_length=MAX_IDS_PER_QUERY,
    ),
    user_service: UserService = Depends(Provide[UserContainer.user_service]),
) -> SuccessResponse[list[UserResponse]]:
    datas = await user_service.get_datas_by_data_ids(data_ids=ids)
    return SuccessResponse(
        data=[UserResponse(**data.model_dump(exclude={"password"})) for data in datas]
    )


# ==========================================================================================


@router.get(
    "/user/{user_id}",
    summary="Get user by ID",
    response_model=SuccessResponse[UserResponse],
    response_model_exclude_none=True,
    response_model_exclude={"pagination"},
)
@inject
async def get_user_by_user_id(
    user_id: int,
    user_service: UserService = Depends(Provide[UserContainer.user_service]),
) -> SuccessResponse[UserResponse]:
    data = await user_service.get_data_by_data_id(data_id=user_id)
    return SuccessResponse(data=UserResponse(**data.model_dump(exclude={"password"})))


# ==========================================================================================


@router.put(
    "/user/{user_id}",
    summary="Update user",
    response_model=SuccessResponse[UserResponse],
    response_model_exclude={"pagination"},
)
@inject
async def update_user_by_user_id(
    user_id: int,
    item: UpdateUserRequest,
    user_service: UserService = Depends(Provide[UserContainer.user_service]),
) -> SuccessResponse[UserResponse]:
    data = await user_service.update_data_by_data_id(data_id=user_id, entity=item)
    return SuccessResponse(data=UserResponse(**data.model_dump(exclude={"password"})))


# ==========================================================================================


@router.delete(
    "/user/{user_id}",
    summary="Delete user",
    response_model=SuccessResponse,
    response_model_exclude={"data", "pagination"},
)
@inject
async def delete_user_by_user_id(
    user_id: int,
    user_service: UserService = Depends(Provide[UserContainer.user_service]),
) -> SuccessResponse:
    success = await user_service.delete_data_by_data_id(data_id=user_id)
    return SuccessResponse(success=success)
