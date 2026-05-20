from datetime import datetime

from pydantic import Field

from src._core.application.dtos.base_request import BaseRequest
from src._core.application.dtos.base_response import BaseResponse


class TodoResponse(BaseResponse):
    id: int
    title: str
    description: str | None = None
    done: bool
    created_at: datetime
    updated_at: datetime


class CreateTodoRequest(BaseRequest):
    title: str = Field(max_length=255)
    description: str | None = Field(default=None, max_length=1000)


class UpdateTodoRequest(BaseRequest):
    title: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    done: bool | None = None
