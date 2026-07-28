"""Unit tests pinning the error-notification hook (#17) added to the global
exception handlers: ``custom_exception_handler`` and
``generic_exception_handler`` must call ``ErrorNotifier.maybe_dispatch`` with
the right status_code/error_code, and must never raise when the DI container
is unavailable (e.g. ``request=None`` in handler-level unit tests, see
``test_guardrail_exception_response.py``)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from src._core.exceptions.base_exception import BaseCustomException
from src._core.exceptions.exception_handlers import (
    custom_exception_handler,
    generic_exception_handler,
    http_exception_handler,
    validation_exception_handler,
)


class FakeErrorNotifier:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def maybe_dispatch(
        self, *, status_code: int, error_code: str, message: str
    ) -> None:
        self.calls.append(
            {"status_code": status_code, "error_code": error_code, "message": message}
        )


def _make_request(error_notifier) -> MagicMock:
    core_container = MagicMock()
    core_container.error_notifier.return_value = error_notifier
    container = MagicMock()
    container.core_container.return_value = core_container
    request = MagicMock()
    request.app.state.container = container
    return request


class TestCustomExceptionHandlerNotification:
    async def test_dispatches_with_exception_status_and_error_code(self):
        error_notifier = FakeErrorNotifier()
        request = _make_request(error_notifier)
        exc = BaseCustomException(
            status_code=503, message="db down", error_code="DB_UNAVAILABLE"
        )

        await custom_exception_handler(request=request, exc=exc)

        assert error_notifier.calls == [
            {
                "status_code": 503,
                "error_code": "DB_UNAVAILABLE",
                "message": str(exc),
            }
        ]

    async def test_no_container_does_not_raise(self):
        # Mirrors test_guardrail_exception_response.py's request=None usage.
        response = await custom_exception_handler(
            request=None,  # type: ignore[arg-type]
            exc=BaseCustomException(status_code=400, message="x", error_code="X"),
        )
        assert response.status_code == 400


class TestGenericExceptionHandlerNotification:
    async def test_unhandled_exception_dispatches_500(self):
        error_notifier = FakeErrorNotifier()
        request = _make_request(error_notifier)

        response = await generic_exception_handler(
            request=request, exc=ValueError("boom")
        )

        assert response.status_code == 500
        assert len(error_notifier.calls) == 1
        assert error_notifier.calls[0]["status_code"] == 500
        assert error_notifier.calls[0]["error_code"] == "INTERNAL_SERVER_ERROR"

    async def test_no_container_does_not_raise(self):
        response = await generic_exception_handler(
            request=None,  # type: ignore[arg-type]
            exc=ValueError("boom"),
        )
        assert response.status_code == 500


class TestNonDispatchingHandlers:
    """Pin the handlers that deliberately never alert (#310, closing #311 R4).

    ``docs/operations/error-notifications.md`` § "What does NOT get alerted"
    promises operators that request-validation failures and ``HTTPException``
    are silent regardless of threshold. Nothing enforced that promise, so
    adding a ``_dispatch_error_notification`` call to either handler would have
    turned a documented guarantee into a lie with no test failing. These are
    negative tests: they assert *absence* of dispatch.
    """

    async def test_validation_errors_never_dispatch(self):
        error_notifier = FakeErrorNotifier()
        request = _make_request(error_notifier)
        exc = RequestValidationError(
            [
                {
                    "loc": ("body", "email"),
                    "msg": "field required",
                    "type": "missing",
                }
            ]
        )

        response = await validation_exception_handler(request=request, exc=exc)

        assert response.status_code == 422
        assert error_notifier.calls == []

    @pytest.mark.parametrize("status_code", [404, 500, 503])
    async def test_http_exception_never_dispatches_at_any_status(self, status_code):
        """Including 500 — a ``raise HTTPException(500)`` is silent by design."""
        error_notifier = FakeErrorNotifier()
        request = _make_request(error_notifier)

        response = await http_exception_handler(
            request=request, exc=StarletteHTTPException(status_code=status_code)
        )

        assert response.status_code == status_code
        assert error_notifier.calls == []
