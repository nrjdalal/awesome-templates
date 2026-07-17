from __future__ import annotations

import pytest

# Test imports from examples.web_search_chatbot package
from examples.web_search_chatbot.domain.dtos.chatbot_dto import (
    ChatMessageDTO,
    ChatReply,
)
from examples.web_search_chatbot.domain.services.chatbot_service import ChatService
from examples.web_search_chatbot.infrastructure.chatbot.pydantic_ai_chatbot import (
    PydanticAIChatbot,
)
from examples.web_search_chatbot.infrastructure.chatbot.stub_chatbot import StubChatbot
from examples.web_search_chatbot.infrastructure.repositories.chatbot_repository import (
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
    """Structural check: agent wiring produces a valid ChatReply.

    Uses TestModel(call_tools=[]) so no tool -- including the real
    duckduckgo_search_tool -- is auto-invoked. Stays fully offline.
    """
    pytest.importorskip("pydantic_ai")
    pytest.importorskip("pydantic_ai.common_tools.duckduckgo")
    from pydantic_ai.models.test import TestModel

    repository = ChatbotRepository(database=test_db)
    model = TestModel(call_tools=[])
    chatbot = PydanticAIChatbot(llm_model=model)
    service = ChatService(chatbot=chatbot, repository=repository)

    message_dto, confidence = await service.reply("Hello AI")

    assert isinstance(message_dto, ChatMessageDTO)
    assert message_dto.id is not None
    assert message_dto.prompt == "Hello AI"
    assert isinstance(message_dto.reply, str)
    assert isinstance(confidence, float)
    assert message_dto.tokens_used >= 0

    retrieved = await service.get_reply(message_dto.id)
    assert retrieved.id == message_dto.id
    assert retrieved.reply == message_dto.reply


@pytest.mark.anyio
async def test_chatbot_invokes_search_tool(test_db, monkeypatch) -> None:
    """Verify the agent actually calls the search tool with the expected args.

    Stays fully offline: the real duckduckgo_search_tool is swapped for a
    fake tool BEFORE the adapter is constructed (the adapter imports it
    lazily inside __init__), so no network call happens. FunctionModel
    forces a tool call on turn 1, then a structured final result on turn 2.
    """
    pytest.importorskip("pydantic_ai")
    pytest.importorskip("pydantic_ai.common_tools.duckduckgo")
    from pydantic_ai.messages import ModelMessage, ModelResponse, ToolCallPart
    from pydantic_ai.models.function import AgentInfo, FunctionModel
    from pydantic_ai.tools import Tool

    calls: list[str] = []

    async def fake_search(query: str) -> str:
        calls.append(query)
        return "fake search result: Python 3.13 is the latest stable release."

    def fake_duckduckgo_search_tool() -> Tool:
        return Tool(
            fake_search,
            name="duckduckgo_search",
            description="Fake search tool for offline tests.",
        )

    monkeypatch.setattr(
        "pydantic_ai.common_tools.duckduckgo.duckduckgo_search_tool",
        fake_duckduckgo_search_tool,
    )

    turn = {"n": 0}

    def agent_function(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        turn["n"] += 1
        if turn["n"] == 1:
            return ModelResponse(
                parts=[
                    ToolCallPart(
                        tool_name="duckduckgo_search",
                        args={"query": "latest Python version"},
                    )
                ]
            )
        return ModelResponse(
            parts=[
                ToolCallPart(
                    tool_name="final_result",
                    args={
                        "reply": "Python 3.13 is the latest stable release.",
                        "confidence": 0.9,
                    },
                )
            ]
        )

    repository = ChatbotRepository(database=test_db)
    model = FunctionModel(agent_function)
    chatbot = PydanticAIChatbot(llm_model=model)
    service = ChatService(chatbot=chatbot, repository=repository)

    message_dto, confidence = await service.reply("What's the latest Python version?")

    assert calls == ["latest Python version"]
    assert isinstance(message_dto, ChatMessageDTO)
    assert isinstance(confidence, float)


def test_chatbot_request_validation() -> None:
    from pydantic import ValidationError

    from examples.web_search_chatbot.interface.server.schemas.chatbot_schema import (
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
