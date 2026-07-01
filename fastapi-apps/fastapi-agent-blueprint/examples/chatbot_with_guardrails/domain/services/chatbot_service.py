from __future__ import annotations

from ...domain.dtos.chatbot_dto import (
    ChatMessageDTO,
    CreateChatMessageDTO,
)
from ...domain.protocols.chatbot_protocol import (
    ChatbotProtocol,
)
from ...domain.protocols.chatbot_repository_protocol import (
    ChatbotRepositoryProtocol,
)


class ChatService:
    """Chat service that orchestrates LLM invocation and database persistence.

    Delegates LLM generation to an injected ``ChatbotProtocol`` implementation
    and DB persistence to an injected ``ChatbotRepositoryProtocol``.
    """

    def __init__(
        self,
        chatbot: ChatbotProtocol,
        repository: ChatbotRepositoryProtocol,
    ) -> None:
        self._chatbot = chatbot
        self._repository = repository

    async def reply(self, prompt: str) -> tuple[ChatMessageDTO, float]:
        """Generate a chat reply, persist the transaction, and return the DTO and confidence.

        Args:
            prompt: The user prompt.

        Returns:
            A tuple of (ChatMessageDTO, confidence).
        """
        chat_reply, usage = await self._chatbot.generate_reply(prompt)
        tokens_used = (usage.input_tokens or 0) + (usage.output_tokens or 0)
        create_dto = CreateChatMessageDTO(
            prompt=prompt,
            reply=chat_reply.reply,
            tokens_used=tokens_used,
        )
        message_dto = await self._repository.insert_data(create_dto)
        return message_dto, chat_reply.confidence

    async def get_reply(self, message_id: int) -> ChatMessageDTO:
        """Retrieve a historical chat message by its database ID.

        Args:
            message_id: The primary key of the chat message.

        Returns:
            The historical ChatMessageDTO.
        """
        return await self._repository.select_data_by_id(data_id=message_id)
