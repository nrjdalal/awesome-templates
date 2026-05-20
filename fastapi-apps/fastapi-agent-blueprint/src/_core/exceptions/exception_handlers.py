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
    return JSONResponse(status_code=exc.status_code, content=content)


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    # Before falling through to a generic 500, check if this is a known
    # LLM/provider SDK exception that should map to a domain error code.
    from src._core.infrastructure.llm.error_mapper import try_map_llm_error

    mapped = try_map_llm_error(exc)
    if mapped is not None:
        content = jsonable_encoder(
            ErrorResponse(
                message=mapped.message,
                error_code=mapped.error_code,
                error_details=mapped.details,
            )
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
    return JSONResponse(status_code=500, content=content)
