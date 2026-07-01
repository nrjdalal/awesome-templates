from datetime import datetime

from pydantic import Field

from src._core.application.dtos.base_request import BaseRequest
from src._core.application.dtos.base_response import BaseResponse


class ChatMemoryRequest(BaseRequest):
    """Validation schema for chat request body."""

    session_id: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="The conversation session identifier",
    )
    prompt: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="The user prompt/message to the chatbot",
    )


class ChatMemoryResponse(BaseResponse):
    """Serialization schema for chatbot memory response."""

    session_id: str = Field(..., description="The conversation session identifier")
    reply: str = Field(..., description="The generated response from the chatbot")
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score of the structured output model",
    )
    tokens_used: int = Field(
        ..., ge=0, description="Calculated total token usage (input + output)"
    )


class ChatMessageResponse(BaseResponse):
    """Serialization schema for a single historical chat message."""

    id: int = Field(..., description="The database primary key")
    session_id: str = Field(..., description="The conversation session identifier")
    role: str = Field(..., description="The message role: user or assistant")
    content: str = Field(..., description="The message content")
    tokens_used: int = Field(..., ge=0, description="Token usage for this message")
    created_at: datetime = Field(
        ..., description="The date/time the message was persisted"
    )
