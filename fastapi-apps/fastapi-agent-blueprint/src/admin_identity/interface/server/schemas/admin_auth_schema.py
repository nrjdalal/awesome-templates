from datetime import datetime

from pydantic import Field

from src._core.application.dtos.base_request import BaseRequest
from src._core.application.dtos.base_response import BaseResponse
from src.admin_identity.domain.dtos.admin_identity_dto import AdminIdentityDTO


class AdminLoginRequest(BaseRequest):
    username: str = Field(min_length=1, max_length=20)
    password: str = Field(min_length=1, max_length=255)


class AdminRefreshTokenRequest(BaseRequest):
    refresh_token: str = Field(min_length=1, max_length=4096)


class AdminLogoutRequest(BaseRequest):
    refresh_token: str = Field(min_length=1, max_length=4096)


class AdminResponse(BaseResponse):
    id: int
    username: str
    full_name: str
    email: str
    permissions: list[str]
    created_at: datetime
    updated_at: datetime


class AdminTokenPairData(BaseResponse):
    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int
    admin: AdminIdentityDTO


class AdminTokenPairResponse(BaseResponse):
    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int
    admin: AdminResponse
