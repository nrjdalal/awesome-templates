from __future__ import annotations

from typing import Any, Final, LiteralString

from ...domain.dtos.chatbot_memory_dto import ChatReply

_INSTRUCTIONS: Final[LiteralString] = (
    "You are a helpful assistant with memory of the conversation. "
    "Use the conversation history to provide context-aware replies."
)


class PydanticAIChatbotMemory:
    """Real LLM-backed chatbot adapter with conversation history support."""

    def __init__(self, llm_model: Any) -> None:
        try:
            from pydantic_ai import Agent
        except ImportError:
            raise ImportError(
                "pydantic-ai is required for the chatbot-with-memory example. "
                "Install it with: uv sync --extra pydantic-ai"
            )

        self._agent: Agent[None, ChatReply] = Agent(
            model=llm_model,
            output_type=ChatReply,
            instructions=_INSTRUCTIONS,
        )

    async def generate_reply(
        self, prompt: str, history: list[dict[str, str]]
    ) -> tuple[ChatReply, Any]:
        """Generate a reply using PydanticAI Agent with structured conversation history.

        Args:
            prompt: The user input text.
            history: Prior conversation turns as role/content dicts.

        Returns:
            A tuple of (ChatReply, usage).
        """
        from pydantic_ai.messages import (
            ModelRequest,
            ModelResponse,
            TextPart,
            UserPromptPart,
        )

        message_history = []
        for turn in history:
            if turn["role"] == "user":
                message_history.append(
                    ModelRequest(parts=[UserPromptPart(content=turn["content"])])
                )
            else:
                message_history.append(
                    ModelResponse(parts=[TextPart(content=turn["content"])])
                )

        result = await self._agent.run(prompt, message_history=message_history)
        return result.output, result.usage()
