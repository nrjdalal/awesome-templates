from typing import Annotated

from pydantic import Field

from src._core.application.dtos.base_request import BaseRequest
from src._core.application.dtos.base_response import BaseResponse

_Category = Annotated[str, Field(min_length=1, max_length=100)]


class ClassifyRequest(BaseRequest):
    """Request schema for text classification."""

    text: str = Field(
        ..., min_length=1, max_length=50_000, description="Text to classify"
    )
    categories: list[_Category] | None = Field(
        default=None, max_length=50, description="Allowed categories (optional)"
    )


class ClassificationResponse(BaseResponse):
    """Response schema for classification result."""

    category: str
    confidence: float
    reasoning: str
