from __future__ import annotations

from ..dtos.chatbot_memory_dto import (
    ChatMessageDTO,
    ConversationTurnDTO,
    CreateChatMessageDTO,
)
from ..protocols.chatbot_memory_protocol import (
    ChatbotMemoryProtocol,
)
from ..protocols.chatbot_memory_repository_protocol import (
    ChatbotMemoryRepositoryProtocol,
)


class ChatMemoryService:
    """Chat service that maintains multi-turn conversation history.

    Loads prior turns from the database and replays them into the agent
    on each call so the LLM has full conversation context.
    """

    def __init__(
        self,
        chatbot: ChatbotMemoryProtocol,
        repository: ChatbotMemoryRepositoryProtocol,
    ) -> None:
        self._chatbot = chatbot
        self._repository = repository

    async def reply(self, session_id: str, prompt: str) -> ConversationTurnDTO:
        """Generate a context-aware reply using full session history.

        1. Load all prior messages for this session from the database.
        2. Replay them as history into the agent.
        3. Persist the new user message and assistant reply.
        4. Return a ConversationTurnDTO with the reply and metadata.

        Args:
            session_id: The conversation session identifier.
            prompt: The new user message.

        Returns:
            ConversationTurnDTO containing the reply and metadata.
        """
        # 1. Load prior history for this session
        _HISTORY_LIMIT = 20
        prior_messages = await self._repository.select_messages_by_session(
            session_id=session_id
        )
        bounded_messages = prior_messages[-_HISTORY_LIMIT:]

        # 2. Build history list for the agent
        history = [
            {"role": msg.role, "content": msg.content} for msg in bounded_messages
        ]

        # 3. Generate reply with history context
        chat_reply, usage = await self._chatbot.generate_reply(
            prompt=prompt, history=history
        )
        tokens_used = (usage.input_tokens or 0) + (usage.output_tokens or 0)

        # 4. Persist user message
        await self._repository.insert_data(
            CreateChatMessageDTO(
                session_id=session_id,
                role="user",
                content=prompt,
                tokens_used=0,
            )
        )

        # 5. Persist assistant reply
        assistant_dto = await self._repository.insert_data(
            CreateChatMessageDTO(
                session_id=session_id,
                role="assistant",
                content=chat_reply.reply,
                tokens_used=tokens_used,
            )
        )

        # Note: tokens_used surfaced on the API response is for educational visibility only.
        # Production usage tracking should go through the `ai_usage` domain (#75).

        return ConversationTurnDTO(
            session_id=session_id,
            user_message=prompt,
            assistant_reply=chat_reply.reply,
            confidence=chat_reply.confidence,
            tokens_used=tokens_used,
            created_at=assistant_dto.created_at,
        )

    async def get_history(self, session_id: str) -> list[ChatMessageDTO]:
        """Retrieve full conversation history for a session.

        Args:
            session_id: The conversation session identifier.

        Returns:
            Ordered list of ChatMessageDTO for the session.
        """
        return await self._repository.select_messages_by_session(session_id=session_id)
