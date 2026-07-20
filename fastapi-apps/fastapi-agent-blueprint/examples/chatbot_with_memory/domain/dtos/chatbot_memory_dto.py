from datetime import datetime

from pydantic import BaseModel, Field


class ChatReply(BaseModel):
    """Structured output schema returned by the PydanticAI agent."""

    reply: str = Field(..., description="The assistant response text")
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="The confidence score of the reply, between 0.0 and 1.0",
    )


class ChatMessageDTO(BaseModel):
    """DTO representing a persisted chat message with session context."""

    id: int
    session_id: str
    role: str
    content: str
    tokens_used: int
    created_at: datetime

    model_config = {"from_attributes": True}


class CreateChatMessageDTO(BaseModel):
    """DTO for persisting a new chat message."""

    session_id: str
    role: str
    content: str
    tokens_used: int


class ConversationTurnDTO(BaseModel):
    """DTO representing a single conversation turn (user + assistant pair)."""

    session_id: str
    user_message: str
    assistant_reply: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    tokens_used: int
    created_at: datetime
