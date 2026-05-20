from src._core.exceptions.base_exception import BaseCustomException


class S3VectorException(BaseCustomException):
    """Base exception for S3 Vectors operations."""

    pass


class S3VectorNotFoundException(S3VectorException):
    def __init__(self) -> None:
        super().__init__(
            status_code=404,
            message="Requested vector not found",
            error_code="S3VECTOR_NOT_FOUND",
        )


class S3VectorIndexNotFoundException(S3VectorException):
    def __init__(self, index_name: str = "") -> None:
        msg = (
            "Vector index not found: " + index_name
            if index_name
            else "Vector index not found"
        )
        super().__init__(
            status_code=404,
            message=msg,
            error_code="S3VECTOR_INDEX_NOT_FOUND",
        )


class S3VectorThrottlingException(S3VectorException):
    def __init__(self) -> None:
        super().__init__(
            status_code=429,
            message="S3 Vectors throughput exceeded",
            error_code="S3VECTOR_THROTTLED",
        )
