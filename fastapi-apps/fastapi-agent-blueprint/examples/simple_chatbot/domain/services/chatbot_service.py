from __future__ import annotations

from ..dtos.chatbot_dto import (
    ChatMessageDTO,
    CreateChatMessageDTO,
)
from ..protocols.chatbot_protocol import ChatbotProtocol
from ..protocols.chatbot_repository_protocol import (
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
        # 1. Call the chatbot protocol to generate the reply and count tokens
        chat_reply, usage = await self._chatbot.generate_reply(prompt)

        # Calculate tokens_used
        tokens_used = (usage.input_tokens or 0) + (usage.output_tokens or 0)

        # 2. Persist the prompt, reply, and tokens used to the database
        # ChatMessageDTO(id, prompt, reply, tokens_used, created_at)
        create_dto = CreateChatMessageDTO(
            prompt=prompt,
            reply=chat_reply.reply,
            tokens_used=tokens_used,
        )
        message_dto = await self._repository.insert_data(create_dto)

        # Note: tokens_used surfaced on the API response is for educational visibility only.
        # Production usage tracking should go through the `ai_usage` domain (#75).

        return message_dto, chat_reply.confidence

    async def get_reply(self, message_id: int) -> ChatMessageDTO:
        """Retrieve a historical chat message by its database ID.

        Args:
            message_id: The primary key of the chat message.

        Returns:
            The historical ChatMessageDTO.
        """
        return await self._repository.select_data_by_id(data_id=message_id)
