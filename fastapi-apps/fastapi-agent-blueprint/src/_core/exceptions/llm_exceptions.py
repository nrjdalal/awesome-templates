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


class PromptInjectionDetected(LLMException):
    """Raised by the input guardrail when a prompt-injection pattern is detected
    in user-supplied input (#197 Phase 3 / #209).

    Carries NO ``details``: ``custom_exception_handler`` serializes
    ``exc.details`` into the client response (``error_details``), so the matched
    rule name must NEVER be passed here — it goes to structlog only. The
    user-facing message is deliberately generic so an attacker cannot probe
    which rule fired.
    """

    def __init__(self) -> None:
        super().__init__(
            status_code=400,
            message="Request blocked by input guardrail.",
            error_code="PROMPT_INJECTION_DETECTED",
            details=None,
        )


class GuardrailBlocked(LLMException):
    """Raised by the output guardrail when the model response violates a policy
    (e.g. fabricated PII not present in the retrieved context) (#197 Phase 3 / #209).

    Like :class:`PromptInjectionDetected`, carries NO ``details`` — the offending
    token / count / type goes to structlog only, never to the client response.
    """

    def __init__(self) -> None:
        super().__init__(
            status_code=422,
            message="Response blocked by output guardrail.",
            error_code="GUARDRAIL_BLOCKED",
            details=None,
        )
