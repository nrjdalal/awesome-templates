"""Unit tests for the centralized admin error handler (#195)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.routing import APIRoute

from src._core.exceptions.base_exception import BaseCustomException
from src._core.infrastructure.admin import error_handler as eh


class _Notify:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def __call__(self, message: str, type: str = "info") -> None:  # noqa: A002
        self.calls.append((message, type))


class _Navigate:
    def __init__(self) -> None:
        self.target: str | None = None

    def to(self, target: str) -> None:
        self.target = target


@pytest.fixture
def fake_admin_runtime(monkeypatch):
    notify = _Notify()
    navigate = _Navigate()
    monkeypatch.setattr(eh, "ui", SimpleNamespace(notify=notify, navigate=navigate))
    monkeypatch.setattr(
        eh, "app", SimpleNamespace(storage=SimpleNamespace(user={"username": "alice"}))
    )
    monkeypatch.setattr(eh, "correlation_id", SimpleNamespace(get=lambda: "cid-123"))
    return notify, navigate


def test_domain_4xx_message_surfaced_as_warning(fake_admin_runtime):
    notify, _ = fake_admin_runtime
    exc = BaseCustomException(
        status_code=409, message="Already exists", error_code="DUP"
    )
    eh.AdminErrorHandler.notify_error(exc)
    assert notify.calls == [("Already exists", "warning")]


def test_domain_5xx_message_is_not_leaked(fake_admin_runtime):
    notify, _ = fake_admin_runtime
    exc = BaseCustomException(
        status_code=500, message="DB host db-prod-01 unreachable", error_code="X"
    )
    eh.AdminErrorHandler.notify_error(exc)
    message, notify_type = notify.calls[0]
    assert notify_type == "negative"
    assert "db-prod-01" not in message
    assert message == eh._GENERIC_MESSAGE


def test_generic_exception_message_is_not_leaked(fake_admin_runtime):
    notify, _ = fake_admin_runtime
    eh.AdminErrorHandler.notify_error(ValueError("secret path /etc/passwd"))
    message, notify_type = notify.calls[0]
    assert notify_type == "negative"
    assert "secret path" not in message
    assert message == eh._GENERIC_MESSAGE


@pytest.mark.asyncio
async def test_handle_non_critical_notifies_without_redirect(fake_admin_runtime):
    notify, navigate = fake_admin_runtime
    await eh.AdminErrorHandler.handle(ValueError("boom"), context="ctx")
    assert navigate.target is None
    assert notify.calls and notify.calls[0][1] == "negative"


@pytest.mark.asyncio
async def test_handle_critical_redirects_with_correlation_id(fake_admin_runtime):
    notify, navigate = fake_admin_runtime
    await eh.AdminErrorHandler.handle(ValueError("boom"), context="ctx", critical=True)
    assert navigate.target == "/admin/error?rid=cid-123"
    assert notify.calls == []  # critical escalates via redirect, no toast


@pytest.mark.asyncio
async def test_decorator_catches_and_delegates(fake_admin_runtime, monkeypatch):
    seen: dict[str, object] = {}

    async def fake_handle(exc, context="", critical=False):
        seen.update(exc=exc, context=context, critical=critical)

    monkeypatch.setattr(eh.AdminErrorHandler, "handle", staticmethod(fake_handle))

    @eh.admin_error_boundary(context="page_ctx")
    async def handler() -> None:
        raise RuntimeError("kaboom")

    await handler()
    assert isinstance(seen["exc"], RuntimeError)
    assert seen["context"] == "page_ctx"
    assert seen["critical"] is False


def test_decorator_preserves_route_parameter_injection():
    """functools.wraps must keep path/query params visible to FastAPI/NiceGUI.

    NiceGUI relies on FastAPI signature introspection to inject @ui.page query
    and path params. The decorator must not hide them behind *args/**kwargs.
    """

    @eh.admin_error_boundary(context="t")
    async def handler(record_id: int, page: int = 1) -> None: ...

    app = FastAPI()
    app.add_api_route("/x/{record_id}", handler)
    route = next(
        r for r in app.routes if isinstance(r, APIRoute) and r.path == "/x/{record_id}"
    )
    path_names = {p.name for p in route.dependant.path_params}
    query_names = {p.name for p in route.dependant.query_params}
    assert "record_id" in path_names
    assert "page" in query_names


def test_current_admin_user_is_none_when_storage_unavailable(monkeypatch):
    class _NoScope:
        @property
        def user(self):
            raise RuntimeError("session storage requires a request scope")

    monkeypatch.setattr(eh, "app", SimpleNamespace(storage=_NoScope()))
    assert eh._current_admin_user() is None


def test_global_handler_logs_without_touching_ui(monkeypatch):
    """The on_exception safety net logs centrally and never calls ui.* (it may
    fire outside a client/slot context)."""
    logged: list[tuple[Exception, str]] = []

    def fake_log(exc, context=""):
        logged.append((exc, context))

    monkeypatch.setattr(eh.AdminErrorHandler, "log_error", staticmethod(fake_log))
    notify = _Notify()
    navigate = _Navigate()
    monkeypatch.setattr(eh, "ui", SimpleNamespace(notify=notify, navigate=navigate))

    exc = RuntimeError("uncaught")
    eh.handle_uncaught_admin_exception(exc)

    assert logged == [(exc, "admin_uncaught")]
    assert notify.calls == []
    assert navigate.target is None
