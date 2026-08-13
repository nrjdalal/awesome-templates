"""A 5xx must leave an exception-level log record (#323).

Probed at `d5c2a1d`: `custom_exception_handler` made no logger call at all, and
`generic_exception_handler` logged only on the *unmapped* path — the
`try_map_llm_error` branch returned first. Meanwhile `Database.session()` puts
the original driver error into `details` only when `settings.is_dev`.

So in stg/prod a 500 reached the client with the wrapped error in **none** of:
the response body, `details`, any log record, or the Slack alert (which receives
the curated `"500 [DB_INTERNAL_ERROR]: Internal database error"`). The only
surviving record was `RequestLogMiddleware`'s `http_request` line, which carries
status and duration but no exception identity.

Most `5xx` raise sites under `src/` do not log before raising. The audit counted
15 of 17; a narrower AST sweep run while fixing this counted 12 of 14. The exact
figure depends on how the sweep decides a `raise` is a 5xx, so treat it as "most
of them". Either way the two that *do* log — `dynamodb_client` and
`vectors/s3/client` — are the house pattern this change aligns with.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from structlog.testing import capture_logs

from src._core.exceptions.base_exception import BaseCustomException
from src._core.exceptions.exception_handlers import (
    custom_exception_handler,
    generic_exception_handler,
    http_exception_handler,
)


def _app() -> FastAPI:
    app = FastAPI()
    # Starlette types `handler` as taking `Exception`; the narrow annotations are
    # the record of which exception each handler serves. Same suppression the
    # production registration carries.
    app.add_exception_handler(BaseCustomException, custom_exception_handler)  # pyright: ignore[reportArgumentType]
    app.add_exception_handler(HTTPException, http_exception_handler)  # pyright: ignore[reportArgumentType]
    app.add_exception_handler(Exception, generic_exception_handler)

    @app.get("/custom/{status}")
    async def _custom(status: int):
        raise BaseCustomException(
            status_code=status, message="curated text", error_code="DB_INTERNAL_ERROR"
        )

    @app.get("/mapped")
    async def _mapped():
        provider = type("APIStatusError", (Exception,), {})
        provider.__module__ = "openai"
        raise provider("Rate limit reached for gpt-4o")

    @app.get("/raw")
    async def _raw():
        raise RuntimeError("deadlock detected on relation users")

    return app


def _exception_records(logs: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    """Records that carry exception identity — the thing an operator greps for."""
    return [
        r
        for r in logs
        if r.get("log_level") in {"error", "critical"}
        or r.get("exc_info")
        or "exception" in str(r.get("event", ""))
    ]


class TestFiveHundredIsLogged:
    @pytest.mark.parametrize("status", [500, 502, 503])
    def test_custom_exception_5xx_produces_an_exception_record(self, status):
        client = TestClient(_app(), raise_server_exceptions=False)
        with capture_logs() as logs:
            resp = client.get(f"/custom/{status}")
        assert resp.status_code == status
        records = _exception_records(logs)
        assert records, (
            f"a {status} left no exception-level log record — the wrapped driver "
            "error exists nowhere in stg/prod"
        )
        assert any("DB_INTERNAL_ERROR" in str(r) for r in records), (
            "the log record does not carry the error_code"
        )

    def test_mapped_provider_error_is_logged_before_the_early_return(self):
        """The `try_map_llm_error` branch returned before `_logger.exception`, so a
        misclassification was invisible. Even a correctly mapped 429 should leave
        a record naming the original exception."""
        client = TestClient(_app(), raise_server_exceptions=False)
        with capture_logs() as logs:
            resp = client.get("/mapped")
        assert resp.status_code == 429
        records = _exception_records(logs)
        assert records, "a mapped provider error left no log record"
        assert any("APIStatusError" in str(r) or "openai" in str(r) for r in records), (
            "the record does not identify the original provider exception"
        )

    def test_unmapped_exception_still_logs(self):
        client = TestClient(_app(), raise_server_exceptions=False)
        with capture_logs() as logs:
            resp = client.get("/raw")
        assert resp.status_code == 500
        assert _exception_records(logs)


class TestFourXXIsNotLoggedAsAnException:
    """Curated 4xx are normal traffic. Logging them at error level would drown the
    signal this change exists to create."""

    @pytest.mark.parametrize("status", [400, 401, 404, 409])
    def test_custom_exception_4xx_produces_no_exception_record(self, status):
        client = TestClient(_app(), raise_server_exceptions=False)
        with capture_logs() as logs:
            resp = client.get(f"/custom/{status}")
        assert resp.status_code == status
        assert not _exception_records(logs), (
            f"a curated {status} was logged at exception level"
        )


class TestResponseBodyIsUnchanged:
    """`security-checklist.md:181-185` mandates that prod responses stay curated.
    This change adds a log record; it must not widen what the client sees."""

    def test_error_details_stay_absent(self):
        client = TestClient(_app(), raise_server_exceptions=False)
        resp = client.get("/custom/500")
        body = resp.json()
        assert body["message"] == "curated text"
        assert body["errorCode"] == "DB_INTERNAL_ERROR"
        assert body.get("errorDetails") is None

    def test_raw_exception_text_does_not_reach_the_client_outside_dev(
        self, monkeypatch
    ):
        """`generic_exception_handler` puts `traceback.format_exc()` into
        `errorDetails` when `settings.is_dev` — documented and deliberate
        (ADR 017). Outside dev it must not, and adding the log record must not
        change that in either direction.
        """
        from src._core import config

        monkeypatch.setattr(type(config.settings), "is_dev", property(lambda _: False))
        client = TestClient(_app(), raise_server_exceptions=False)
        resp = client.get("/raw")
        assert resp.status_code == 500
        assert "deadlock" not in resp.text, (
            "the raw driver message reached the response body outside dev"
        )
        assert resp.json()["errorDetails"] is None

    def test_dev_still_gets_the_trace(self, monkeypatch):
        """The other half of the same contract — this is why the assertion above
        has to be environment-scoped rather than absolute."""
        from src._core import config

        monkeypatch.setattr(type(config.settings), "is_dev", property(lambda _: True))
        client = TestClient(_app(), raise_server_exceptions=False)
        resp = client.get("/raw")
        assert "deadlock" in resp.text
