from __future__ import annotations

from dependency_injector import containers, providers

from src._core.config import settings
from src._core.domain.services.rag_pipeline import RagPipeline
from src._core.infrastructure.rag.pydantic_ai_answer_agent import PydanticAIAnswerAgent
from src._core.infrastructure.rag.stub_answer_agent import StubAnswerAgent
from src._core.infrastructure.rag.stub_embedder import StubEmbedder
from src.docs.domain.services.docs_query_service import DocsQueryService
from src.docs.domain.services.document_service import DocumentService
from src.docs.infrastructure.repositories.document_repository import DocumentRepository
from src.docs.infrastructure.vectors.document_chunk_in_memory_store import (
    DocumentChunkInMemoryVectorStore,
)
from src.docs.infrastructure.vectors.document_chunk_s3_store import (
    DocumentChunkS3VectorStore,
)


def _vector_store_selector() -> str:
    return (settings.vector_store_type or "inmemory").lower().strip()


def _embedder_selector() -> str:
    return "real" if settings.embedding_model_name else "stub"


def _answer_agent_selector() -> str:
    return "real" if settings.llm_model_name else "stub"


class DocsContainer(containers.DeclarativeContainer):
    """DI container for the docs domain.

    Graceful degradation:
    - Stub embedder when ``EMBEDDING_*`` is unset.
    - Stub answer agent when ``LLM_*`` is unset.
    - Vector backend selected by ``VECTOR_STORE_TYPE`` (default inmemory).
    """

    core_container = providers.DependenciesContainer()

    document_repository = providers.Singleton(
        DocumentRepository,
        database=core_container.database,
    )

    chunk_vector_store = providers.Selector(
        _vector_store_selector,
        inmemory=providers.Singleton(DocumentChunkInMemoryVectorStore),
        s3vectors=providers.Singleton(
            DocumentChunkS3VectorStore,
            s3vector_client=core_container.s3vector_client,
            bucket_name=settings.s3vectors_bucket_name or "",
        ),
    )

    embedder = providers.Selector(
        _embedder_selector,
        real=core_container.embedding_client,
        stub=providers.Singleton(StubEmbedder),
    )

    answer_agent = providers.Selector(
        _answer_agent_selector,
        real=providers.Singleton(
            PydanticAIAnswerAgent,
            llm_model=core_container.llm_model,
        ),
        stub=providers.Singleton(StubAnswerAgent),
    )

    rag_pipeline = providers.Singleton(
        RagPipeline,
        embedder=embedder,
        vector_store=chunk_vector_store,
        answer_agent=answer_agent,
    )

    document_service = providers.Factory(
        DocumentService,
        document_repository=document_repository,
        embedder=embedder,
        chunk_vector_store=chunk_vector_store,
    )

    docs_query_service = providers.Factory(
        DocsQueryService,
        rag_pipeline=rag_pipeline,
    )

    # Alias for admin auto-discovery (``{domain}_service`` convention).
    docs_service = document_service
