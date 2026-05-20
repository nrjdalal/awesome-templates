from __future__ import annotations

from typing import Any

from pydantic import Field

from src._core.domain.value_objects.agent_usage_record import PromptSource
from src._core.domain.value_objects.value_object import ValueObject


class PromptSnapshot(ValueObject):
    """Immutable metadata for a resolved prompt at execution time."""

    name: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1)
    version: str | None = Field(default=None, max_length=50)
    source: PromptSource
    external_ref: str | None = Field(default=None, max_length=500)
    metadata: dict[str, Any] = Field(default_factory=dict)
