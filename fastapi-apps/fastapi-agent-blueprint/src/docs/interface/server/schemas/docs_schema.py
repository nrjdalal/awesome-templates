from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field

from src._core.application.dtos.base_request import BaseRequest
from src._core.application.dtos.base_response import BaseResponse

# ----------------------------------------------------------------------
# Document CRUD
# ----------------------------------------------------------------------


class CreateDocumentRequest(BaseRequest):
    title: str = Field(..., min_length=1, max_length=255)
    content: str = Field(..., min_length=1, max_length=1_000_000)
    source: str | None = Field(default=None, max_length=1024)


class UpdateDocumentRequest(BaseRequest):
    title: str | None = Field(default=None, max_length=255)
    content: str | None = Field(default=None, max_length=1_000_000)
    source: str | None = Field(default=None, max_length=1024)
    chunk_count: int | None = Field(default=None, ge=0)


class DocumentResponse(BaseResponse):
    id: int
    title: str
    content: str
    source: str | None = None
    chunk_count: int
    created_at: datetime
    updated_at: datetime


# ----------------------------------------------------------------------
# Query
# ----------------------------------------------------------------------


class QueryRequest(BaseRequest):
    question: str = Field(
        ..., min_length=1, max_length=2_000, description="User question"
    )
    top_k: int = Field(default=5, ge=1, le=50, description="Chunks to retrieve")
    filters: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Optional S3-Vectors-compatible filter dict "
            "(e.g. {'source_id': {'$eq': '1'}})"
        ),
    )


class CitationResponse(BaseResponse):
    source_id: str
    source_title: str
    excerpt: str
    distance: float | None = None


class QueryResponse(BaseResponse):
    answer: str
    citations: list[CitationResponse]
    retrieved_count: int
