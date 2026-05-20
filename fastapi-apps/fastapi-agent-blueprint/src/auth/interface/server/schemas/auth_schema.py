from pydantic import EmailStr, Field

from src._core.application.dtos.base_request import BaseRequest
from src._core.application.dtos.base_response import BaseResponse
from src.user.domain.dtos.user_dto import UserDTO
from src.user.interface.server.schemas.user_schema import UserResponse


class RegisterRequest(BaseRequest):
    username: str = Field(min_length=1, max_length=20)
    full_name: str = Field(min_length=1, max_length=255)
    email: EmailStr = Field(max_length=255)
    password: str = Field(min_length=1, max_length=255)


class LoginRequest(BaseRequest):
    username: str = Field(min_length=1, max_length=20)
    password: str = Field(min_length=1, max_length=255)


class RefreshTokenRequest(BaseRequest):
    refresh_token: str = Field(min_length=1, max_length=4096)


class LogoutRequest(BaseRequest):
    refresh_token: str = Field(min_length=1, max_length=4096)


class TokenPairData(BaseResponse):
    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int
    user: UserDTO


class TokenPairResponse(BaseResponse):
    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int
    user: UserResponse
