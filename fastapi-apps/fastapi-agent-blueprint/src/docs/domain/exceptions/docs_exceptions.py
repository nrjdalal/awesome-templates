from __future__ import annotations

from src._core.exceptions.base_exception import BaseCustomException


class DocumentNotFoundException(BaseCustomException):
    def __init__(self, document_id: int) -> None:
        super().__init__(
            status_code=404,
            message=f"Document with ID [ {document_id} ] not found",
            error_code="DOCS_DOCUMENT_NOT_FOUND",
        )


class IngestionFailedException(BaseCustomException):
    def __init__(self, reason: str) -> None:
        super().__init__(
            status_code=500,
            message=f"Document ingestion failed: {reason}",
            error_code="DOCS_INGESTION_FAILED",
        )


class QueryFailedException(BaseCustomException):
    def __init__(self, reason: str) -> None:
        super().__init__(
            status_code=500,
            message=f"Docs query failed: {reason}",
            error_code="DOCS_QUERY_FAILED",
        )
