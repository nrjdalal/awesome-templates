from __future__ import annotations

import pytest

# Test imports from examples.simple_chatbot package
from examples.simple_chatbot.domain.dtos.chatbot_dto import ChatMessageDTO, ChatReply
from examples.simple_chatbot.domain.services.chatbot_service import ChatService
from examples.simple_chatbot.infrastructure.chatbot.pydantic_ai_chatbot import (
    PydanticAIChatbot,
)
from examples.simple_chatbot.infrastructure.chatbot.stub_chatbot import StubChatbot
from examples.simple_chatbot.infrastructure.repositories.chatbot_repository import (
    ChatbotRepository,
)


@pytest.mark.anyio
async def test_chatbot_stub_flow(test_db) -> None:
    # 1. Setup repository and stub chatbot
    repository = ChatbotRepository(database=test_db)
    chatbot = StubChatbot()
    service = ChatService(chatbot=chatbot, repository=repository)

    # 2. Call the chatbot service
    message_dto, confidence = await service.reply("Hello stub")

    # 3. Assertions
    assert isinstance(message_dto, ChatMessageDTO)
    assert message_dto.id is not None
    assert message_dto.prompt == "Hello stub"
    assert "stub" in message_dto.reply.lower()
    assert message_dto.tokens_used == 0
    assert confidence == 0.0

    # 4. Assert DB retrieval
    retrieved = await service.get_reply(message_dto.id)
    assert retrieved.id == message_dto.id
    assert retrieved.prompt == message_dto.prompt
    assert retrieved.reply == message_dto.reply


@pytest.mark.anyio
async def test_chatbot_real_agent_flow(test_db) -> None:
    # Verify that pydantic_ai is installed (skipped otherwise)
    pytest.importorskip("pydantic_ai")
    from pydantic_ai.models.test import TestModel

    # 1. Setup repository and PydanticAI chatbot with TestModel
    repository = ChatbotRepository(database=test_db)
    model = TestModel()
    chatbot = PydanticAIChatbot(llm_model=model)
    service = ChatService(chatbot=chatbot, repository=repository)

    # 2. Call the chatbot service
    message_dto, confidence = await service.reply("Hello AI")

    # 3. Assertions
    assert isinstance(message_dto, ChatMessageDTO)
    assert message_dto.id is not None
    assert message_dto.prompt == "Hello AI"
    assert isinstance(message_dto.reply, str)
    assert isinstance(confidence, float)
    assert message_dto.tokens_used >= 0

    # 4. Assert DB retrieval
    retrieved = await service.get_reply(message_dto.id)
    assert retrieved.id == message_dto.id
    assert retrieved.reply == message_dto.reply


def test_chatbot_request_validation() -> None:
    from pydantic import ValidationError

    from examples.simple_chatbot.interface.server.schemas.chatbot_schema import (
        ChatRequest,
    )

    # 1. Valid prompt should pass
    req = ChatRequest(prompt="Hello")
    assert req.prompt == "Hello"

    # 2. Empty prompt should fail (min_length=1)
    with pytest.raises(ValidationError):
        ChatRequest(prompt="")

    # 3. Prompt > 1000 chars should fail (max_length=1000)
    with pytest.raises(ValidationError):
        ChatRequest(prompt="a" * 1001)


def test_chat_reply_confidence_bounds() -> None:
    """ChatReply.confidence must be within [0.0, 1.0].

    The bound lives on the PydanticAI agent output schema, so an out-of-range
    model confidence is rejected at output-validation time -- before the service
    persists the turn (no orphan row, no duplicate on client retry). See #294.
    """
    from pydantic import ValidationError

    # Boundary values are accepted
    assert ChatReply(reply="ok", confidence=0.0).confidence == 0.0
    assert ChatReply(reply="ok", confidence=1.0).confidence == 1.0

    # Out-of-range values are rejected
    with pytest.raises(ValidationError):
        ChatReply(reply="ok", confidence=1.2)
    with pytest.raises(ValidationError):
        ChatReply(reply="ok", confidence=-0.1)


@pytest.mark.anyio
async def test_out_of_range_confidence_fails_before_persistence(
    test_db, monkeypatch
) -> None:
    """An out-of-range model confidence fails inside the agent run -- before any DB write.

    Pins the #294 fix end-to-end through the real adapter and service:
    FunctionModel forces confidence=1.2, the agent's output validation rejects
    it (retries exhaust into UnexpectedModelBehavior), and the service never
    reaches its insert -- no orphan row, no duplicate on client retry.
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

    repository = ChatbotRepository(database=test_db)
    insert_calls: list[object] = []
    original_insert = repository.insert_data

    async def counting_insert(dto):  # noqa: ANN001, ANN202
        insert_calls.append(dto)
        return await original_insert(dto)

    monkeypatch.setattr(repository, "insert_data", counting_insert)

    chatbot = PydanticAIChatbot(llm_model=FunctionModel(agent_function))
    service = ChatService(chatbot=chatbot, repository=repository)

    with pytest.raises(UnexpectedModelBehavior):
        await service.reply("Hello AI")

    assert insert_calls == []
