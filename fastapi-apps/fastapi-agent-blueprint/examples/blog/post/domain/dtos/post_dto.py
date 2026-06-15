from datetime import datetime

from pydantic import BaseModel


class PostDTO(BaseModel):
    id: int
    author_id: int
    title: str
    body: str
    created_at: datetime
    updated_at: datetime
