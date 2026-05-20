from src._core.exceptions.base_exception import BaseCustomException


class LLMException(BaseCustomException):
    """Base exception for LLM operations."""


class LLMAuthenticationException(LLMException):
    def __init__(self) -> None:
        super().__init__(
            status_code=401,
            message="LLM API authentication failed",
            error_code="LLM_AUTH_FAILED",
        )


class LLMRateLimitException(LLMException):
    def __init__(self) -> None:
        super().__init__(
            status_code=429,
            message="LLM API rate limit exceeded",
            error_code="LLM_RATE_LIMITED",
        )


class LLMModelNotFoundException(LLMException):
    def __init__(self, model_id: str = "") -> None:
        msg = f"LLM model not found: {model_id}" if model_id else "LLM model not found"
        super().__init__(
            status_code=404,
            message=msg,
            error_code="LLM_MODEL_NOT_FOUND",
        )


class LLMContextLengthExceededException(LLMException):
    def __init__(self, tokens: int = 0, max_tokens: int = 0) -> None:
        msg = (
            f"LLM context length exceeded: {tokens} tokens (max {max_tokens})"
            if tokens
            else "LLM context length exceeded"
        )
        super().__init__(
            status_code=400,
            message=msg,
            error_code="LLM_CONTEXT_LENGTH_EXCEEDED",
        )
