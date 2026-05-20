"""LLM provider exception mapper (ACL — Anti-Corruption Layer).

Translates provider SDK exceptions (PydanticAI, boto3, openai, anthropic)
to domain-layer LLM exceptions. This module belongs in infrastructure because
it knows provider SDK class names — domain services must not know them.

Usage:
- Domain services propagate exceptions without catching.
- The server ``generic_exception_handler`` calls ``try_map_llm_error`` to
  convert known provider exceptions before falling through to the 500 handler.
- Infrastructure adapters (e.g. ``PydanticAIClassifier``) may call
  ``map_llm_error`` directly when they need the NoReturn guarantee.
"""

from __future__ import annotations

from typing import NoReturn

from src._core.exceptions.llm_exceptions import (
    LLMAuthenticationException,
    LLMContextLengthExceededException,
    LLMException,
    LLMModelNotFoundException,
    LLMRateLimitException,
)

_RATE_LIMIT_NAMES = frozenset(
    {
        "ratelimiterror",
        "ratelimitexception",
        "throttlingexception",
        "toomanyrequestsexception",
        "throttlederror",
        "quotaexceeded",
    }
)
_AUTH_NAMES = frozenset(
    {
        "authenticationerror",
        "unauthorizederror",
        "permissiondeniederror",
        "invalidapikeyerror",
        "authorizationerror",
    }
)
_CONTEXT_NAMES = frozenset(
    {
        "contextlengtherror",
        "contextlengthexceeded",
        "maxtokensexceeded",
    }
)
_NOT_FOUND_NAMES = frozenset(
    {
        "modelnotfounderror",
        "modelnotfoundexception",
    }
)


def _classify(exc: Exception) -> LLMException | None:
    """Classify an exception as a known LLM provider error.

    Returns a domain LLMException instance, or None if the exception is not
    a recognisable provider error (caller should treat it as a generic 500).
    """
    type_name = type(exc).__name__.lower().replace("_", "")
    error_str = str(exc).lower()

    if (
        type_name in _RATE_LIMIT_NAMES
        or "throttl" in error_str
        or ("rate" in error_str and "limit" in error_str)
    ):
        return LLMRateLimitException()
    if (
        type_name in _AUTH_NAMES
        or "authentication" in error_str
        or "unauthorized" in error_str
    ):
        return LLMAuthenticationException()
    if type_name in _CONTEXT_NAMES or (
        "context" in error_str and ("length" in error_str or "window" in error_str)
    ):
        return LLMContextLengthExceededException()
    if type_name in _NOT_FOUND_NAMES or (
        "model" in error_str and "not found" in error_str
    ):
        return LLMModelNotFoundException()

    return None


def try_map_llm_error(exc: Exception) -> LLMException | None:
    """Try to map a provider exception to a domain LLM exception.

    Returns a domain exception instance if ``exc`` is a recognisable provider
    error, or ``None`` if it is not — allowing the caller to apply a fallback.
    """
    return _classify(exc)


def map_llm_error(exc: Exception) -> NoReturn:
    """Map a provider exception to a domain LLM exception — always raises.

    Prefer ``try_map_llm_error`` in HTTP exception handlers where you want
    to fall through to a generic 500 for unrecognised errors.
    Use this in infrastructure adapters that must guarantee a domain exception.
    """
    mapped = _classify(exc)
    if mapped is not None:
        raise mapped from exc
    raise LLMException(
        status_code=502,
        message="LLM operation failed",
        error_code="LLM_OPERATION_FAILED",
    ) from exc
