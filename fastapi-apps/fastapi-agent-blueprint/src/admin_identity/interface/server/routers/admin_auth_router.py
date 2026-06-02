from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends

from src._core.application.dtos.base_response import SuccessResponse
from src.admin_identity.application.use_cases.admin_auth_use_case import (
    AdminAuthUseCase,
)
from src.admin_identity.infrastructure.di.admin_identity_container import (
    AdminIdentityContainer,
)
from src.admin_identity.interface.server.schemas.admin_auth_schema import (
    AdminLoginRequest,
    AdminLogoutRequest,
    AdminRefreshTokenRequest,
    AdminResponse,
    AdminTokenPairResponse,
)

router = APIRouter()


def _token_response(token_data) -> AdminTokenPairResponse:
    return AdminTokenPairResponse(
        access_token=token_data.access_token,
        refresh_token=token_data.refresh_token,
        token_type=token_data.token_type,
        expires_in=token_data.expires_in,
        admin=AdminResponse(
            **token_data.admin.model_dump(
                exclude={"password", "password_temporary", "is_bootstrap_admin"}
            )
        ),
    )


@router.post(
    "/admin/login",
    summary="Admin login (admin token realm)",
    response_model=SuccessResponse[AdminTokenPairResponse],
    response_model_exclude={"pagination"},
)
@inject
async def admin_login(
    item: AdminLoginRequest,
    admin_auth_use_case: AdminAuthUseCase = Depends(
        Provide[AdminIdentityContainer.admin_auth_use_case]
    ),
) -> SuccessResponse[AdminTokenPairResponse]:
    token_data = await admin_auth_use_case.login(item)
    return SuccessResponse(data=_token_response(token_data))


@router.post(
    "/admin/refresh",
    summary="Refresh admin token pair",
    response_model=SuccessResponse[AdminTokenPairResponse],
    response_model_exclude={"pagination"},
)
@inject
async def admin_refresh(
    item: AdminRefreshTokenRequest,
    admin_auth_use_case: AdminAuthUseCase = Depends(
        Provide[AdminIdentityContainer.admin_auth_use_case]
    ),
) -> SuccessResponse[AdminTokenPairResponse]:
    token_data = await admin_auth_use_case.refresh(item)
    return SuccessResponse(data=_token_response(token_data))


@router.post(
    "/admin/logout",
    summary="Admin logout",
    response_model=SuccessResponse[bool],
    response_model_exclude={"pagination"},
)
@inject
async def admin_logout(
    item: AdminLogoutRequest,
    admin_auth_use_case: AdminAuthUseCase = Depends(
        Provide[AdminIdentityContainer.admin_auth_use_case]
    ),
) -> SuccessResponse[bool]:
    success = await admin_auth_use_case.logout(item)
    return SuccessResponse(data=success)
