from datetime import datetime

from pydantic import EmailStr, Field

from src._core.application.dtos.base_request import BaseRequest
from src._core.application.dtos.base_response import BaseResponse


class UserResponse(BaseResponse):
    id: int
    username: str
    full_name: str
    email: str
    created_at: datetime
    updated_at: datetime


class CreateUserRequest(BaseRequest):
    username: str = Field(min_length=1, max_length=20)
    full_name: str = Field(min_length=1, max_length=255)
    email: EmailStr = Field(max_length=255)
    password: str = Field(min_length=1, max_length=255)


class UpdateUserRequest(BaseRequest):
    username: str | None = Field(default=None, min_length=1, max_length=20)
    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    email: EmailStr | None = Field(default=None, max_length=255)
    password: str | None = Field(default=None, min_length=1, max_length=255)
