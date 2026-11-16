from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class PromptVersionDTO(BaseModel):
    name: str
    version: int
    content: str
    created_by: str
    created_at: datetime | None = None


class ActivePromptDTO(BaseModel):
    """The active version of one prompt, joined with its text."""

    name: str
    version: int
    content: str
    activated_by: str
    activated_at: datetime | None = None
