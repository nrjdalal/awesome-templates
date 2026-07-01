from typing import Annotated

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, Path

from src._core.application.dtos.base_response import SuccessResponse

from ....domain.services.chatbot_memory_service import (
    ChatMemoryService,
)
from ....infrastructure.di.chatbot_with_memory_container import (
    ChatbotWithMemoryContainer,
)
from ..schemas.chatbot_memory_schema import (
    ChatMemoryRequest,
    ChatMemoryResponse,
    ChatMessageResponse,
)

router = APIRouter()


@router.post(
    "/chat/memory",
    summary="Send a message to the memory-aware chatbot",
    response_model=SuccessResponse[ChatMemoryResponse],
    response_model_exclude={"pagination"},
)
@inject
async def chat_memory_reply(
    request: ChatMemoryRequest,
    chat_memory_service: ChatMemoryService = Depends(
        Provide[ChatbotWithMemoryContainer.chat_memory_service]
    ),
) -> SuccessResponse[ChatMemoryResponse]:
    """Execute memory-aware chatbot agent and persist the turn to DB."""
    turn_dto = await chat_memory_service.reply(
        session_id=request.session_id,
        prompt=request.prompt,
    )
    return SuccessResponse(
        data=ChatMemoryResponse(
            session_id=turn_dto.session_id,
            reply=turn_dto.assistant_reply,
            confidence=turn_dto.confidence,
            tokens_used=turn_dto.tokens_used,
        )
    )


@router.get(
    "/chat/memory/{session_id}",
    summary="Get conversation history for a session",
    response_model=SuccessResponse[list[ChatMessageResponse]],
    response_model_exclude={"pagination"},
)
@inject
async def get_chat_memory_history(
    session_id: Annotated[str, Path(min_length=1, max_length=128)],
    limit: int = 20,
    offset: int = 0,
    chat_memory_service: ChatMemoryService = Depends(
        Provide[ChatbotWithMemoryContainer.chat_memory_service]
    ),
) -> SuccessResponse[list[ChatMessageResponse]]:
    """Fetch conversation history for a session, paginated by limit/offset."""
    messages = await chat_memory_service.get_history(session_id=session_id)
    paginated = messages[offset : offset + limit]
    return SuccessResponse(
        data=[
            ChatMessageResponse(
                id=msg.id,
                session_id=msg.session_id,
                role=msg.role,
                content=msg.content,
                tokens_used=msg.tokens_used,
                created_at=msg.created_at,
            )
            for msg in paginated
        ]
    )
