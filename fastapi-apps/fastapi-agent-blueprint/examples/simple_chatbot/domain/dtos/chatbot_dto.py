from datetime import datetime

from pydantic import BaseModel, Field


class ChatReply(BaseModel):
    """Structured output schema returned by the PydanticAI agent."""

    reply: str = Field(..., description="The assistant response text")
    confidence: float = Field(
        ..., description="The confidence score of the reply, between 0.0 and 1.0"
    )


class ChatMessageDTO(BaseModel):
    """DTO representing the persisted chat message."""

    id: int
    prompt: str
    reply: str
    tokens_used: int
    created_at: datetime

    model_config = {"from_attributes": True}


class CreateChatMessageDTO(BaseModel):
    """DTO representing a new chat message to be persisted."""

    prompt: str
    reply: str
    tokens_used: int
