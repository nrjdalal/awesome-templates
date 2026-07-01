from typing import Protocol

from src._core.domain.protocols.repository_protocol import BaseRepositoryProtocol

from ..dtos.chatbot_memory_dto import ChatMessageDTO


class ChatbotMemoryRepositoryProtocol(BaseRepositoryProtocol[ChatMessageDTO], Protocol):
    """Protocol for chatbot memory message database operations."""

    async def select_messages_by_session(self, session_id: str) -> list[ChatMessageDTO]:
        """Retrieve all messages for a given session ordered by creation time.

        Args:
            session_id: The session identifier.

        Returns:
            Ordered list of ChatMessageDTO for the session.
        """
        ...
