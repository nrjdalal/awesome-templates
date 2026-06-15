from datetime import datetime

from pydantic import Field

from src._core.application.dtos.base_request import BaseRequest
from src._core.application.dtos.base_response import BaseResponse


class AuthorResponse(BaseResponse):
    id: int
    display_name: str
    created_at: datetime
    updated_at: datetime


class CreateAuthorRequest(BaseRequest):
    display_name: str = Field(max_length=255)


class UpdateAuthorRequest(BaseRequest):
    display_name: str | None = Field(default=None, max_length=255)
