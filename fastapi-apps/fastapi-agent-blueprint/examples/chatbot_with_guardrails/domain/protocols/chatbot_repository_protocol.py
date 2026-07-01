from typing import Protocol

from src._core.domain.protocols.repository_protocol import BaseRepositoryProtocol

from ...domain.dtos.chatbot_dto import ChatMessageDTO


class ChatbotRepositoryProtocol(BaseRepositoryProtocol[ChatMessageDTO], Protocol):
    """Protocol for the chatbot message database operations."""

    pass
