from __future__ import annotations

from typing import Any, Final, LiteralString

from ...domain.dtos.chatbot_dto import ChatReply

_INSTRUCTIONS: Final[LiteralString] = (
    "You are a helpful assistant with access to a web search tool. "
    "Use it when the user asks about current events, facts you are "
    "unsure of, or anything that may require up-to-date information."
)


class PydanticAIChatbot:
    """Real LLM-backed chatbot adapter using PydanticAI Agent with web search."""

    def __init__(self, llm_model: Any) -> None:
        try:
            from pydantic_ai import Agent
        except ImportError:
            raise ImportError(
                "pydantic-ai is required for the web-search-chatbot example. "
                "Install it with: uv sync --extra pydantic-ai"
            )

        try:
            from pydantic_ai.common_tools.duckduckgo import duckduckgo_search_tool
        except ImportError:
            raise ImportError(
                "pydantic-ai-slim[duckduckgo] is required for the "
                "web-search-chatbot example's real search tool. "
                "Install it with: uv sync --extra pydantic-ai-duckduckgo"
            )

        self._agent: Agent[None, ChatReply] = Agent(
            model=llm_model,
            output_type=ChatReply,
            instructions=_INSTRUCTIONS,
            tools=[duckduckgo_search_tool()],
        )

    async def generate_reply(self, prompt: str) -> tuple[ChatReply, Any]:
        """Generate a reply using PydanticAI Agent, invoking web search as needed.

        Args:
            prompt: The user input text.

        Returns:
            A tuple of (ChatReply, usage).
        """
        result = await self._agent.run(prompt)
        return result.output, result.usage()
