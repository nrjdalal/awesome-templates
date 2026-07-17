from typing import Annotated

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, Path

from src._core.application.dtos.base_response import SuccessResponse

from ....domain.services.chatbot_service import ChatService
from ....infrastructure.di.web_search_chatbot_container import (
    WebSearchChatbotContainer,
)
from ..schemas.chatbot_schema import (
    ChatHistoryResponse,
    ChatRequest,
    ChatResponse,
)

router = APIRouter()


@router.post(
    "/chat",
    summary="Send a message to the chatbot",
    response_model=SuccessResponse[ChatResponse],
    response_model_exclude={"pagination"},
)
@inject
async def chat_reply(
    request: ChatRequest,
    chatbot_service: ChatService = Depends(
        Provide[WebSearchChatbotContainer.chat_service]
    ),
) -> SuccessResponse[ChatResponse]:
    """Execute chatbot agent, persist prompt and reply to DB, and return the reply."""
    message_dto, confidence = await chatbot_service.reply(prompt=request.prompt)
    return SuccessResponse(
        data=ChatResponse(
            reply=message_dto.reply,
            confidence=confidence,
            tokens_used=message_dto.tokens_used,
        )
    )


@router.get(
    "/chat/{chat_id}",
    summary="Get a historical chatbot reply",
    response_model=SuccessResponse[ChatHistoryResponse],
    response_model_exclude={"pagination"},
)
@inject
async def get_chat_message(
    chat_id: Annotated[int, Path(ge=1)],
    chatbot_service: ChatService = Depends(
        Provide[WebSearchChatbotContainer.chat_service]
    ),
) -> SuccessResponse[ChatHistoryResponse]:
    """Fetch a historical chat message and its metadata from database by ID."""
    message_dto = await chatbot_service.get_reply(message_id=chat_id)
    return SuccessResponse(
        data=ChatHistoryResponse(
            id=message_dto.id,
            prompt=message_dto.prompt,
            reply=message_dto.reply,
            tokens_used=message_dto.tokens_used,
            created_at=message_dto.created_at,
        )
    )
