from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pydantic import BaseModel, Field

from src._core.domain.dtos.rag import BaseChunkDTO, CitationDTO, QueryAnswerDTO

_SYSTEM_PROMPT = (
    "You are a precise RAG assistant. "
    "Answer the user's question using ONLY the provided context chunks. "
    "Cite sources as [source_title]. "
    "If the context doesn't contain the answer, say so plainly."
)


class _AgentAnswer(BaseModel):
    """Structured output requested from the LLM.

    Citations are assembled deterministically from the retrieval result
    (see ``PydanticAIAnswerAgent.answer``) rather than fabricated by the
    model, so the agent is asked only for the answer text.
    """

    answer: str = Field(..., description="The answer text")


class PydanticAIAnswerAgent:
    """Real LLM-backed RAG answerer via PydanticAI."""

    def __init__(self, llm_model: Any) -> None:
        try:
            from pydantic_ai import Agent
        except ImportError:
            raise ImportError(
                "pydantic-ai is required for the RAG answer agent. "
                "Install it with: uv sync --extra pydantic-ai"
            )

        self._agent: Agent[None, _AgentAnswer] = Agent(
            model=llm_model,
            output_type=_AgentAnswer,
            system_prompt=_SYSTEM_PROMPT,
        )

    async def answer(
        self,
        question: str,
        context_chunks: Sequence[BaseChunkDTO],
    ) -> QueryAnswerDTO:
        prompt = _format_prompt(question, list(context_chunks))
        result = await self._agent.run(prompt)
        citations = [CitationDTO.from_chunk(chunk) for chunk in context_chunks]
        return QueryAnswerDTO(answer=result.output.answer, citations=citations)


def _format_prompt(question: str, chunks: list[BaseChunkDTO]) -> str:
    if not chunks:
        return (
            f"Question: {question}\n\n"
            "Context: (no relevant chunks retrieved)\n\n"
            "If the context does not answer the question, say so plainly."
        )
    context_blocks = [f"[{chunk.source_title}]\n{chunk.content}" for chunk in chunks]
    context = "\n\n---\n\n".join(context_blocks)
    return f"Context:\n{context}\n\nQuestion: {question}"
