from datetime import datetime

from pydantic import BaseModel


class LinkDTO(BaseModel):
    id: int
    short_code: str
    target_url: str
    expires_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
