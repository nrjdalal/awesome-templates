from typing import Generic, TypeVar

from src._core.application.dtos.base_config import ApiConfig


class PaginationInfo(ApiConfig):
    current_page: int
    page_size: int
    total_items: int
    total_pages: int
    has_previous: bool
    has_next: bool
    next_page: int | None = None
    previous_page: int | None = None


class ExistsData(ApiConfig):
    exists: bool


class CursorPaginationInfo(ApiConfig):
    """Cursor-based pagination metadata for DynamoDB-backed endpoints."""

    next_cursor: str | None = None
    page_size: int
    has_next: bool


ReturnType = TypeVar("ReturnType")


class BaseResponse(ApiConfig):
    pass


class SuccessResponse(ApiConfig, Generic[ReturnType]):
    success: bool = True
    message: str = "Request processed successfully"
    data: ReturnType | None = None
    pagination: PaginationInfo | None = None


class ErrorResponse(ApiConfig):
    success: bool = False
    message: str = "Request failed"
    error_code: str | None = None
    error_details: dict | None = None
