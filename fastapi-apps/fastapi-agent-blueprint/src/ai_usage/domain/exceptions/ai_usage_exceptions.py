from src._core.exceptions.base_exception import BaseCustomException


class AiUsageImmutableException(BaseCustomException):
    def __init__(self) -> None:
        super().__init__(
            status_code=409,
            message="AI usage logs are append-only",
            error_code="AI_USAGE_IMMUTABLE",
        )
