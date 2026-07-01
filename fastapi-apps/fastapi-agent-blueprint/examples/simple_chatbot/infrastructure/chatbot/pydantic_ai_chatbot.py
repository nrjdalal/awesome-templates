from __future__ import annotations

from typing import Any, Final, LiteralString

from ...domain.dtos.chatbot_dto import ChatReply

_INSTRUCTIONS: Final[LiteralString] = "You are a helpful assistant."


class PydanticAIChatbot:
    """Real LLM-backed chatbot adapter using PydanticAI Agent."""

    def __init__(self, llm_model: Any) -> None:
        try:
            from pydantic_ai import Agent
        except ImportError:
            raise ImportError(
                "pydantic-ai is required for the simple-chatbot example. "
                "Install it with: uv sync --extra pydantic-ai"
            )

        self._agent: Agent[None, ChatReply] = Agent(
            model=llm_model,
            output_type=ChatReply,
            instructions=_INSTRUCTIONS,
        )

    async def generate_reply(self, prompt: str) -> tuple[ChatReply, Any]:
        """Generate a reply using PydanticAI Agent.

        Args:
            prompt: The user input text.

        Returns:
            A tuple of (ChatReply, usage).
        """
        result = await self._agent.run(prompt)
        return result.output, result.usage()
