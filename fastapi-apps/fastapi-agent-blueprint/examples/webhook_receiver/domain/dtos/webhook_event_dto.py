from datetime import datetime

from pydantic import BaseModel


class WebhookEventDTO(BaseModel):
    id: int
    source: str
    payload: dict
    status: str
    received_at: datetime
    processed_at: datetime | None = None
