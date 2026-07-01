from sqlalchemy import select

from src._core.infrastructure.persistence.rdb.base_repository import BaseRepository
from src._core.infrastructure.persistence.rdb.database import Database

from ...domain.dtos.chatbot_memory_dto import ChatMessageDTO
from ...domain.protocols.chatbot_memory_repository_protocol import (
    ChatbotMemoryRepositoryProtocol,
)
from ..database.models.chatbot_memory_model import (
    ChatMemoryMessageModel,
)


class ChatbotMemoryRepository(
    BaseRepository[ChatMessageDTO], ChatbotMemoryRepositoryProtocol
):
    """SQLAlchemy repository for chatbot memory messages."""

    def __init__(self, database: Database) -> None:
        super().__init__(
            database=database,
            model=ChatMemoryMessageModel,
            return_entity=ChatMessageDTO,
        )

    async def select_messages_by_session(self, session_id: str) -> list[ChatMessageDTO]:
        """Retrieve all messages for a session ordered by creation time.

        Args:
            session_id: The session identifier.

        Returns:
            Ordered list of ChatMessageDTO for the session.
        """
        async with self.database.session() as session:
            result = await session.execute(
                select(ChatMemoryMessageModel)
                .where(ChatMemoryMessageModel.session_id == session_id)
                .order_by(ChatMemoryMessageModel.created_at, ChatMemoryMessageModel.id)
            )
            rows = result.scalars().all()
            return [
                ChatMessageDTO.model_validate(row, from_attributes=True) for row in rows
            ]
