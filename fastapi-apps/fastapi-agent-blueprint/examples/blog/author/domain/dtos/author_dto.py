from datetime import datetime

from pydantic import BaseModel


class AuthorDTO(BaseModel):
    id: int
    display_name: str
    created_at: datetime
    updated_at: datetime
