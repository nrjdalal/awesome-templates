from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class DocumentDTO(BaseModel):
    """RAG document metadata DTO.

    Represents a single ingested document. The raw ``content`` field is
    kept on the domain DTO so the worker-based re-ingestion path can
    reconstruct chunks without hitting an external store.
    """

    id: int = Field(..., description="Document unique identifier")
    title: str = Field(..., description="Document title")
    content: str = Field(..., description="Raw document content")
    source: str | None = Field(default=None, description="Optional source URL or path")
    chunk_count: int = Field(default=0, description="Number of chunks produced")
    created_at: datetime = Field(..., description="Created at")
    updated_at: datetime = Field(..., description="Updated at")
