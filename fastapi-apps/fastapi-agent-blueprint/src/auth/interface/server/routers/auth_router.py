from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends

from src._core.application.dtos.base_response import SuccessResponse
from src.auth.application.use_cases.auth_use_case import AuthUseCase
from src.auth.infrastructure.di.auth_container import AuthContainer
from src.auth.interface.server.dependencies.auth_dependencies import get_current_user
from src.auth.interface.server.schemas.auth_schema import (
    LoginRequest,
    LogoutRequest,
    RefreshTokenRequest,
    RegisterRequest,
    TokenPairResponse,
)
from src.user.domain.dtos.user_dto import UserDTO
from src.user.interface.server.schemas.user_schema import UserResponse

router = APIRouter()


def _token_response(token_data) -> TokenPairResponse:
    return TokenPairResponse(
        access_token=token_data.access_token,
        refresh_token=token_data.refresh_token,
        token_type=token_data.token_type,
        expires_in=token_data.expires_in,
        user=UserResponse(**token_data.user.model_dump(exclude={"password", "role"})),
    )


@router.post(
    "/auth/register",
    summary="Register user",
    response_model=SuccessResponse[TokenPairResponse],
    response_model_exclude={"pagination"},
)
@inject
async def register(
    item: RegisterRequest,
    auth_use_case: AuthUseCase = Depends(Provide[AuthContainer.auth_use_case]),
) -> SuccessResponse[TokenPairResponse]:
    token_data = await auth_use_case.register(item)
    return SuccessResponse(data=_token_response(token_data))


@router.post(
    "/auth/login",
    summary="Login",
    response_model=SuccessResponse[TokenPairResponse],
    response_model_exclude={"pagination"},
)
@inject
async def login(
    item: LoginRequest,
    auth_use_case: AuthUseCase = Depends(Provide[AuthContainer.auth_use_case]),
) -> SuccessResponse[TokenPairResponse]:
    token_data = await auth_use_case.login(item)
    return SuccessResponse(data=_token_response(token_data))


@router.post(
    "/auth/refresh",
    summary="Refresh token pair",
    response_model=SuccessResponse[TokenPairResponse],
    response_model_exclude={"pagination"},
)
@inject
async def refresh(
    item: RefreshTokenRequest,
    auth_use_case: AuthUseCase = Depends(Provide[AuthContainer.auth_use_case]),
) -> SuccessResponse[TokenPairResponse]:
    token_data = await auth_use_case.refresh(item)
    return SuccessResponse(data=_token_response(token_data))


@router.post(
    "/auth/logout",
    summary="Logout",
    response_model=SuccessResponse[bool],
    response_model_exclude={"pagination"},
)
@inject
async def logout(
    item: LogoutRequest,
    auth_use_case: AuthUseCase = Depends(Provide[AuthContainer.auth_use_case]),
) -> SuccessResponse[bool]:
    success = await auth_use_case.logout(item)
    return SuccessResponse(data=success)


@router.get(
    "/auth/me",
    summary="Get current user",
    response_model=SuccessResponse[UserResponse],
    response_model_exclude={"pagination"},
)
async def me(
    current_user: UserDTO = Depends(get_current_user),
) -> SuccessResponse[UserResponse]:
    return SuccessResponse(
        data=UserResponse(**current_user.model_dump(exclude={"password", "role"}))
    )
