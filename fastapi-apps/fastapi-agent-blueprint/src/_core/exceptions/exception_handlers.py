import traceback

import structlog
from fastapi import Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from src._core.application.dtos.base_response import ErrorResponse
from src._core.config import settings
from src._core.exceptions.base_exception import BaseCustomException

_logger = structlog.stdlib.get_logger("src._core.exceptions")

# Status at or above which a curated exception is also an operational event worth
# an exception-level log record. Named rather than inlined so the worker path can
# share the same boundary (see taskiq_middleware._synthetic_status_code).
_SERVER_ERROR_FLOOR = 500


def _dispatch_error_notification(
    request: Request, *, status_code: int, error_code: str, message: str
) -> None:
    """Fire-and-forget Slack/Discord alert (#17).

    Never raises — a failure here (missing container, disabled notifier,
    webhook error) must not turn into a second error for the caller. The
    actual severity/cooldown gating and non-blocking dispatch live in
    ``ErrorNotifier``; this only has to find it.
    """
    try:
        error_notifier = request.app.state.container.core_container().error_notifier()
        error_notifier.maybe_dispatch(
            status_code=status_code, error_code=error_code, message=message
        )
    except AttributeError:
        # No app/container wired (e.g. handler invoked directly in a unit
        # test) — nothing to notify through, not a real error.
        return
    except Exception:
        _logger.warning("error_notifier_dispatch_failed", exc_info=True)


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    errors = [
        {
            "field": ".".join(str(loc) for loc in error["loc"]),
            "message": error["msg"],
            "type": error["type"],
        }
        for error in exc.errors()
    ]

    content = jsonable_encoder(
        ErrorResponse(
            message="Request validation failed",
            error_code="VALIDATION_ERROR",
            error_details={"errors": errors},
        )
    )
    return JSONResponse(status_code=422, content=content)


async def http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    content = jsonable_encoder(
        ErrorResponse(
            message=exc.detail if isinstance(exc.detail, str) else "HTTP error",
            error_code=f"HTTP_{exc.status_code}",
        )
    )
    return JSONResponse(status_code=exc.status_code, content=content)


async def custom_exception_handler(
    request: Request, exc: BaseCustomException
) -> JSONResponse:
    content = jsonable_encoder(
        ErrorResponse(
            message=exc.message,
            error_code=exc.error_code,
            error_details=exc.details,
        )
    )
    # A curated 5xx still means something broke. Without this record the wrapped
    # cause exists nowhere in stg/prod: the response is curated by design, the
    # notification receives that same curated text, and ``details`` carries the
    # original only when ``settings.is_dev``. Curated 4xx are normal traffic and
    # stay unlogged — logging them at error level would bury this signal.
    if exc.status_code >= _SERVER_ERROR_FLOOR:
        _logger.exception(
            "custom_exception",
            exc_info=exc,
            exception_type=type(exc).__name__,
            error_code=exc.error_code,
            status_code=exc.status_code,
        )
    _dispatch_error_notification(
        request,
        status_code=exc.status_code,
        error_code=exc.error_code,
        message=str(exc),
    )
    return JSONResponse(status_code=exc.status_code, content=content)


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    # Before falling through to a generic 500, check if this is a known
    # LLM/provider SDK exception that should map to a domain error code.
    from src._core.infrastructure.llm.error_mapper import try_map_llm_error

    mapped = try_map_llm_error(exc)
    if mapped is not None:
        # Log before the early return. This branch used to bypass
        # ``_logger.exception`` below, so a provider error — or, before the
        # mapper was gated on provider modules, a *misclassified* ordinary
        # exception — produced a 4xx with no trace anywhere. The original ``exc``
        # is what matters here; ``mapped`` is a translation of it.
        _logger.exception(
            "mapped_provider_exception",
            exc_info=exc,
            exception_type=type(exc).__name__,
            exception_module=type(exc).__module__,
            mapped_error_code=mapped.error_code,
            mapped_status_code=mapped.status_code,
        )
        content = jsonable_encoder(
            ErrorResponse(
                message=mapped.message,
                error_code=mapped.error_code,
                error_details=mapped.details,
            )
        )
        _dispatch_error_notification(
            request,
            status_code=mapped.status_code,
            error_code=mapped.error_code,
            message=str(mapped),
        )
        return JSONResponse(status_code=mapped.status_code, content=content)

    # Structured exception log — ``format_exc_info`` in the configured
    # processor pipeline renders the traceback for us, so we just pass
    # ``exc_info=True``. In dev the renderer is ``ConsoleRenderer`` (human-
    # readable with coloured traceback); in prod it's ``JSONRenderer``.
    _logger.exception(
        "unhandled_exception",
        exc_info=exc,
        exception_type=type(exc).__name__,
    )

    error_details = {"trace": traceback.format_exc()} if settings.is_dev else None

    content = jsonable_encoder(
        ErrorResponse(
            message="Internal server error",
            error_code="INTERNAL_SERVER_ERROR",
            error_details=error_details,
        )
    )
    _dispatch_error_notification(
        request,
        status_code=500,
        error_code="INTERNAL_SERVER_ERROR",
        message=f"{type(exc).__name__}: {exc}",
    )
    return JSONResponse(status_code=500, content=content)
