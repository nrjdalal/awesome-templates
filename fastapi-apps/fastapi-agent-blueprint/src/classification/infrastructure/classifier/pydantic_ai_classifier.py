from __future__ import annotations

from typing import Any

from src.classification.domain.dtos.classification_dto import ClassificationDTO

_SYSTEM_PROMPT = (
    "You are a precise text classifier. "
    "Classify the given text into one of the provided categories. "
    "Return your confidence score (0 to 1) and a brief reasoning."
)


class PydanticAIClassifier:
    """Real LLM-backed classifier via PydanticAI Agent."""

    def __init__(self, llm_model: Any) -> None:
        try:
            from pydantic_ai import Agent
        except ImportError:
            raise ImportError(
                "pydantic-ai is required for classification. "
                "Install it with: uv sync --extra pydantic-ai"
            )

        self._agent: Agent[None, ClassificationDTO] = Agent(
            model=llm_model,
            output_type=ClassificationDTO,
            system_prompt=_SYSTEM_PROMPT,
        )

    async def classify(
        self,
        text: str,
        categories: list[str] | None = None,
    ) -> ClassificationDTO:
        prompt = text
        if categories:
            cats = ", ".join(categories)
            prompt = f"Categories: {cats}\n\nText: {text}"

        result = await self._agent.run(prompt)
        return result.output
