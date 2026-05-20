from src._core.exceptions.base_exception import BaseCustomException


class EmbeddingException(BaseCustomException):
    """Base exception for embedding operations."""

    pass


class EmbeddingRateLimitException(EmbeddingException):
    def __init__(self) -> None:
        super().__init__(
            status_code=429,
            message="Embedding API rate limit exceeded",
            error_code="EMBEDDING_RATE_LIMITED",
        )


class EmbeddingAuthenticationException(EmbeddingException):
    def __init__(self) -> None:
        super().__init__(
            status_code=401,
            message="Embedding API authentication failed",
            error_code="EMBEDDING_AUTH_FAILED",
        )


class EmbeddingModelNotFoundException(EmbeddingException):
    def __init__(self, model_id: str = "") -> None:
        msg = (
            "Embedding model not found: " + model_id
            if model_id
            else "Embedding model not found"
        )
        super().__init__(
            status_code=404,
            message=msg,
            error_code="EMBEDDING_MODEL_NOT_FOUND",
        )


class EmbeddingInputTooLongException(EmbeddingException):
    def __init__(
        self, input_length: int, max_length: int, unit: str = "tokens"
    ) -> None:
        super().__init__(
            status_code=400,
            message=(
                f"Embedding input too long: {input_length} {unit} "
                f"(max {max_length} {unit})"
            ),
            error_code="EMBEDDING_INPUT_TOO_LONG",
        )
