from datetime import datetime

from src._core.application.dtos.base_payload import BasePayload


class UserTestPayload(BasePayload):
    id: int
    username: str
    full_name: str
    email: str
    created_at: datetime
    updated_at: datetime
