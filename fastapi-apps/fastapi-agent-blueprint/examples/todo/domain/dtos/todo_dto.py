from datetime import datetime

from pydantic import BaseModel


class TodoDTO(BaseModel):
    id: int
    title: str
    description: str | None = None
    done: bool = False
    created_at: datetime
    updated_at: datetime
