"""Unit tests for the chatbot-with-memory example."""

from __future__ import annotations

import pytest

from examples.chatbot_with_memory.domain.dtos.chatbot_memory_dto import (
    ChatMessageDTO,
    ConversationTurnDTO,
)
from examples.chatbot_with_memory.domain.services.chatbot_memory_service import (
    ChatMemoryService,
)
from examples.chatbot_with_memory.infrastructure.chatbot.pydantic_ai_chatbot_memory import (
    PydanticAIChatbotMemory,
)
from examples.chatbot_with_memory.infrastructure.chatbot.stub_chatbot_memory import (
    StubChatbotMemory,
)
from examples.chatbot_with_memory.infrastructure.repositories.chatbot_memory_repository import (
    ChatbotMemoryRepository,
)


@pytest.mark.anyio
async def test_stub_single_turn(test_db) -> None:
    """Stub chatbot returns a reply and persists user + assistant messages."""
    repository = ChatbotMemoryRepository(database=test_db)
    chatbot = StubChatbotMemory()
    service = ChatMemoryService(chatbot=chatbot, repository=repository)

    turn = await service.reply(session_id="session-1", prompt="Hello")

    assert isinstance(turn, ConversationTurnDTO)
    assert turn.session_id == "session-1"
    assert turn.user_message == "Hello"
    assert "stub" in turn.assistant_reply.lower()
    assert turn.tokens_used == 0
    assert turn.confidence == 0.0


@pytest.mark.anyio
async def test_stub_history_grows_across_turns(test_db) -> None:
    """Each turn persists messages and history is passed to the next call."""
    repository = ChatbotMemoryRepository(database=test_db)
    chatbot = StubChatbotMemory()
    service = ChatMemoryService(chatbot=chatbot, repository=repository)

    session_id = "session-history"

    # First turn — no prior history
    turn1 = await service.reply(session_id=session_id, prompt="Turn one")
    assert "0 prior turn" in turn1.assistant_reply

    # Second turn — 2 messages in history (user + assistant from turn 1)
    turn2 = await service.reply(session_id=session_id, prompt="Turn two")
    assert "2 prior turn" in turn2.assistant_reply

    # Third turn — 4 messages in history
    turn3 = await service.reply(session_id=session_id, prompt="Turn three")
    assert "4 prior turn" in turn3.assistant_reply


@pytest.mark.anyio
async def test_get_history_returns_all_messages(test_db) -> None:
    """get_history returns all persisted messages for a session in order."""
    repository = ChatbotMemoryRepository(database=test_db)
    chatbot = StubChatbotMemory()
    service = ChatMemoryService(chatbot=chatbot, repository=repository)

    session_id = "session-retrieve"

    await service.reply(session_id=session_id, prompt="First message")
    await service.reply(session_id=session_id, prompt="Second message")

    history = await service.get_history(session_id=session_id)

    assert len(history) == 4  # 2 turns × 2 messages (user + assistant)
    assert all(isinstance(msg, ChatMessageDTO) for msg in history)
    assert history[0].role == "user"
    assert history[0].content == "First message"
    assert history[1].role == "assistant"


@pytest.mark.anyio
async def test_real_agent_flow(test_db) -> None:
    """PydanticAI TestModel integration test — skipped without pydantic_ai."""
    pytest.importorskip("pydantic_ai")
    from pydantic_ai.models.test import TestModel

    repository = ChatbotMemoryRepository(database=test_db)
    model = TestModel()
    chatbot = PydanticAIChatbotMemory(llm_model=model)
    service = ChatMemoryService(chatbot=chatbot, repository=repository)

    turn = await service.reply(session_id="session-real", prompt="Hello AI")

    assert isinstance(turn, ConversationTurnDTO)
    assert turn.session_id == "session-real"
    assert isinstance(turn.assistant_reply, str)
    assert isinstance(turn.confidence, float)
    assert turn.tokens_used >= 0


def test_chat_memory_request_validation() -> None:
    """Schema validation — empty fields and oversized inputs are rejected."""
    from pydantic import ValidationError

    from examples.chatbot_with_memory.interface.server.schemas.chatbot_memory_schema import (
        ChatMemoryRequest,
    )

    # Valid request
    req = ChatMemoryRequest(session_id="abc", prompt="Hello")
    assert req.session_id == "abc"
    assert req.prompt == "Hello"

    # Empty prompt
    with pytest.raises(ValidationError):
        ChatMemoryRequest(session_id="abc", prompt="")

    # Empty session_id
    with pytest.raises(ValidationError):
        ChatMemoryRequest(session_id="", prompt="Hello")

    # Prompt too long
    with pytest.raises(ValidationError):
        ChatMemoryRequest(session_id="abc", prompt="a" * 1001)

    # session_id too long
    with pytest.raises(ValidationError):
        ChatMemoryRequest(session_id="a" * 129, prompt="Hello")


def test_confidence_bounds() -> None:
    """confidence must be within [0.0, 1.0] on both the agent output and the turn DTO.

    The bound on ``ChatReply`` (the PydanticAI agent output schema) rejects an
    out-of-range model confidence at output-validation time -- before the service
    persists the two turn rows (no orphan rows, no duplicates on client retry).
    ``ConversationTurnDTO`` carries the same bound as defense-in-depth. See #294.
    """
    from datetime import datetime

    from pydantic import ValidationError

    from examples.chatbot_with_memory.domain.dtos.chatbot_memory_dto import ChatReply

    # ChatReply (agent output) -- boundaries accepted, out-of-range rejected
    assert ChatReply(reply="ok", confidence=0.0).confidence == 0.0
    assert ChatReply(reply="ok", confidence=1.0).confidence == 1.0
    with pytest.raises(ValidationError):
        ChatReply(reply="ok", confidence=1.2)
    with pytest.raises(ValidationError):
        ChatReply(reply="ok", confidence=-0.1)

    # ConversationTurnDTO carrier -- same bound
    def _turn(confidence: float) -> ConversationTurnDTO:
        return ConversationTurnDTO(
            session_id="s",
            user_message="hi",
            assistant_reply="yo",
            confidence=confidence,
            tokens_used=0,
            created_at=datetime(2026, 1, 1),
        )

    assert _turn(0.0).confidence == 0.0
    assert _turn(1.0).confidence == 1.0
    with pytest.raises(ValidationError):
        _turn(1.2)
    with pytest.raises(ValidationError):
        _turn(-0.1)


@pytest.mark.anyio
async def test_out_of_range_confidence_fails_before_persistence(test_db) -> None:
    """An out-of-range model confidence fails inside the agent run -- before any DB write.

    Pins the #294 fix end-to-end through the real adapter and service:
    FunctionModel forces confidence=1.2, the agent's output validation rejects
    it (retries exhaust into UnexpectedModelBehavior), and the service never
    reaches its two inserts -- neither the user nor the assistant row is
    persisted, so a client retry cannot duplicate the turn.
    """
    pytest.importorskip("pydantic_ai")
    from pydantic_ai import UnexpectedModelBehavior
    from pydantic_ai.messages import ModelMessage, ModelResponse, ToolCallPart
    from pydantic_ai.models.function import AgentInfo, FunctionModel

    def agent_function(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        return ModelResponse(
            parts=[
                ToolCallPart(
                    tool_name="final_result",
                    args={"reply": "ok", "confidence": 1.2},
                )
            ]
        )

    repository = ChatbotMemoryRepository(database=test_db)
    chatbot = PydanticAIChatbotMemory(llm_model=FunctionModel(agent_function))
    service = ChatMemoryService(chatbot=chatbot, repository=repository)

    with pytest.raises(UnexpectedModelBehavior):
        await service.reply(session_id="session-out-of-range", prompt="Hello AI")

    # Neither the user nor the assistant row was persisted
    assert await service.get_history(session_id="session-out-of-range") == []
