from datetime import datetime

from pydantic import Field

from src._core.application.dtos.base_request import BaseRequest
from src._core.application.dtos.base_response import BaseResponse


class LinkResponse(BaseResponse):
    id: int
    short_code: str
    target_url: str
    expires_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class CreateLinkRequest(BaseRequest):
    short_code: str = Field(min_length=1, max_length=64)
    target_url: str = Field(min_length=1, max_length=2048)
    expires_at: datetime | None = None


class UpdateLinkRequest(BaseRequest):
    target_url: str | None = Field(default=None, min_length=1, max_length=2048)
    expires_at: datetime | None = None
