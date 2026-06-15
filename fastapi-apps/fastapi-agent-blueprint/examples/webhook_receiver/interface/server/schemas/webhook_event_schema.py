from datetime import datetime

from pydantic import Field

from src._core.application.dtos.base_request import BaseRequest
from src._core.application.dtos.base_response import BaseResponse


class WebhookEventResponse(BaseResponse):
    id: int
    source: str
    payload: dict
    status: str
    received_at: datetime
    processed_at: datetime | None = None


class CreateWebhookRequest(BaseRequest):
    source: str = Field(
        ..., max_length=255, description="Webhook source name (e.g. stripe)"
    )
    payload: dict = Field(..., description="Webhook event payload")


class UpdateWebhookEventRequest(BaseRequest):
    source: str | None = Field(default=None, max_length=255)
    payload: dict | None = None
    status: str | None = Field(default=None, max_length=50)
    processed_at: datetime | None = None
