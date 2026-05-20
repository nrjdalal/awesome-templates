from __future__ import annotations

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, Query

from src._core.application.dtos.base_response import SuccessResponse
from src.docs.domain.services.docs_query_service import DocsQueryService
from src.docs.domain.services.document_service import DocumentService
from src.docs.infrastructure.di.docs_container import DocsContainer
from src.docs.interface.server.schemas.docs_schema import (
    CitationResponse,
    CreateDocumentRequest,
    DocumentResponse,
    QueryRequest,
    QueryResponse,
)
from src.docs.interface.worker.tasks.document_ingestion_task import (
    ingest_document_task,
)

router = APIRouter()


# ==========================================================================================
# Document CRUD
# ==========================================================================================


@router.post(
    "/docs/documents",
    summary="Create and ingest a docs document",
    response_model=SuccessResponse[DocumentResponse],
    response_model_exclude={"pagination"},
)
@inject
async def create_document(
    item: CreateDocumentRequest,
    document_service: DocumentService = Depends(
        Provide[DocsContainer.document_service]
    ),
) -> SuccessResponse[DocumentResponse]:
    # Small documents ingest inline so the client gets a ready-to-query
    # response. Large documents fall back to the worker to keep the
    # request bounded; chunk_count stays at 0 until the task finishes.
    if document_service.should_ingest_sync(item.content):
        data = await document_service.create_data(entity=item)
    else:
        data = await document_service.create_without_ingestion(entity=item)
        await ingest_document_task.kiq(document_id=data.id)
    return SuccessResponse(data=DocumentResponse(**data.model_dump()))


@router.get(
    "/docs/documents",
    summary="List docs documents",
    response_model=SuccessResponse[list[DocumentResponse]],
)
@inject
async def list_documents(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, alias="pageSize", ge=1, le=100),
    document_service: DocumentService = Depends(
        Provide[DocsContainer.document_service]
    ),
) -> SuccessResponse[list[DocumentResponse]]:
    datas, pagination = await document_service.get_datas(page=page, page_size=page_size)
    return SuccessResponse(
        data=[DocumentResponse(**data.model_dump()) for data in datas],
        pagination=pagination,
    )


@router.get(
    "/docs/documents/{document_id}",
    summary="Get docs document by ID",
    response_model=SuccessResponse[DocumentResponse],
    response_model_exclude={"pagination"},
)
@inject
async def get_document(
    document_id: int,
    document_service: DocumentService = Depends(
        Provide[DocsContainer.document_service]
    ),
) -> SuccessResponse[DocumentResponse]:
    data = await document_service.get_data_by_data_id(data_id=document_id)
    return SuccessResponse(data=DocumentResponse(**data.model_dump()))


@router.delete(
    "/docs/documents/{document_id}",
    summary="Delete docs document and its chunks",
    response_model=SuccessResponse,
    response_model_exclude={"data", "pagination"},
)
@inject
async def delete_document(
    document_id: int,
    document_service: DocumentService = Depends(
        Provide[DocsContainer.document_service]
    ),
) -> SuccessResponse:
    success = await document_service.delete_data_by_data_id(data_id=document_id)
    return SuccessResponse(success=success)


# ==========================================================================================
# Query
# ==========================================================================================


@router.post(
    "/docs/query",
    summary="Ask a question over ingested documents",
    response_model=SuccessResponse[QueryResponse],
    response_model_exclude={"pagination"},
)
@inject
async def query_docs(
    item: QueryRequest,
    docs_query_service: DocsQueryService = Depends(
        Provide[DocsContainer.docs_query_service]
    ),
) -> SuccessResponse[QueryResponse]:
    answer, retrieved_count = await docs_query_service.answer_question(
        question=item.question,
        top_k=item.top_k,
        filters=item.filters,
    )
    return SuccessResponse(
        data=QueryResponse(
            answer=answer.answer,
            citations=[CitationResponse(**c.model_dump()) for c in answer.citations],
            retrieved_count=retrieved_count,
        )
    )
