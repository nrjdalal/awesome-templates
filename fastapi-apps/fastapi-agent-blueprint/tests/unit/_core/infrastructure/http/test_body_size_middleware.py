"""Request bodies are bounded, on both paths a caller can use (#322).

Nothing bounded them before. FastAPI reads and JSON-parses the whole body before
validation — or even authentication — can reject it. Measured against
`POST /v1/user`, which requires an admin token:

    1MB  -> 401 in 0.05s
    16MB -> 401 in 0.07s
    64MB -> 401 in 0.28s      <- the body was read before the 401

The `Field(max_length=100)` bounds that shipped earlier in #322 cap how much
*work* a valid body triggers. This caps how much *body* the process holds.

Why the chunked case gets its own tests
--------------------------------------
A `Content-Length` check alone is not a control. HTTP/1.1 chunked encoding sends
no `Content-Length`, so a header-only check is skipped entirely by a caller who
omits it — verified against this app, `Content-Length present: False`. The
middleware therefore also counts streamed bytes.

Rejecting mid-stream is where the first implementation was wrong: responding from
the receive side while the app still intends to respond produces two
`http.response.start` messages. httpx's transport fails on
`assert not response_started`; uvicorn raises "Unexpected message". `send` is
wrapped so the app's late response is genuinely dropped, which the tests below
pin from both directions.
"""

from __future__ import annotations

import json

import pytest
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from src._core.infrastructure.http.body_size_middleware import BodySizeLimitMiddleware

LIMIT = 1024


def _build_app(*, max_bytes: int = LIMIT) -> Starlette:
    """A minimal app that reads the whole body, like a FastAPI route would."""

    async def echo(request: Request) -> JSONResponse:
        body = await request.body()
        return JSONResponse({"read": len(body)})

    app = Starlette(routes=[Route("/echo", echo, methods=["POST", "PUT", "GET"])])
    app.add_middleware(BodySizeLimitMiddleware, max_bytes=max_bytes)
    return app


def _raw_scope(
    *, headers: list | None = None, method: str = "POST", path: str = "/echo"
) -> dict:
    return {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": method,
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "root_path": "",
        "scheme": "http",
        "headers": headers or [],
        "client": ("127.0.0.1", 1234),
        "server": ("testserver", 80),
    }


@pytest.fixture
def client() -> TestClient:
    return TestClient(_build_app())


class TestTheContentLengthPath:
    def test_a_body_under_the_limit_passes_through(self, client):
        resp = client.post("/echo", content=b"x" * (LIMIT - 1))
        assert resp.status_code == 200
        assert resp.json()["read"] == LIMIT - 1

    def test_a_body_exactly_at_the_limit_passes(self, client):
        """The limit is a maximum, not a strict bound. Pinned because an
        off-by-one here silently rejects a documented-legal payload."""
        resp = client.post("/echo", content=b"x" * LIMIT)
        assert resp.status_code == 200

    def test_a_body_over_the_limit_is_rejected(self, client):
        resp = client.post("/echo", content=b"x" * (LIMIT + 1))
        assert resp.status_code == 413

    def test_the_rejection_body_matches_the_error_response_shape(self, client):
        """Clients parse every other error through `ErrorResponse`. This runs
        outside the exception handlers, so the shape is hand-rolled and worth
        pinning."""
        resp = client.post("/echo", content=b"x" * (LIMIT * 4))
        payload = json.loads(resp.text)
        assert payload["success"] is False
        assert payload["errorCode"] == "REQUEST_BODY_TOO_LARGE"
        assert payload["errorDetails"] is None
        assert str(LIMIT) in payload["message"]
        assert resp.headers["content-type"] == "application/json"

    def test_the_app_never_sees_an_oversized_body(self):
        """The point of the middleware: not just the status code, but that the
        handler was never invoked with the payload."""
        seen: list[int] = []

        async def record(request: Request) -> JSONResponse:
            body = await request.body()
            seen.append(len(body))
            return JSONResponse({"read": len(body)})

        app = Starlette(routes=[Route("/r", record, methods=["POST"])])
        app.add_middleware(BodySizeLimitMiddleware, max_bytes=LIMIT)

        resp = TestClient(app).post("/r", content=b"x" * (LIMIT * 8))
        assert resp.status_code == 413
        assert seen == [], f"the handler read {seen} bytes of a rejected body"


class TestTheNoContentLengthPath:
    """The bypass a header-only check would leave open.

    Scope note, and it is narrower than it first looks: Starlette's `TestClient`
    **coalesces** a generator body into a single ASGI `http.request` message. A
    3-byte + 4-byte generator arrives as one 7-byte message with no
    Content-Length. So these tests cover "no Content-Length" — the property that
    defeats a header-only check — but NOT multi-message accumulation. That is
    covered separately at the raw ASGI level below, where the message boundaries
    are ours to choose. Asserting the real HTTP/1.1 chunked wire format would take
    a socket-level test against a live uvicorn, which this file does not attempt.
    """

    @staticmethod
    def _chunks(total: int, size: int = 256):
        sent = 0
        while sent < total:
            n = min(size, total - sent)
            yield b"x" * n
            sent += n

    def test_an_oversized_body_with_no_content_length_is_rejected(self, client):
        resp = client.post("/echo", content=self._chunks(LIMIT * 6))
        assert resp.status_code == 413

    def test_a_body_under_the_limit_with_no_content_length_passes(self, client):
        resp = client.post("/echo", content=self._chunks(LIMIT // 2))
        assert resp.status_code == 200
        assert resp.json()["read"] == LIMIT // 2

    def test_the_request_carried_no_content_length(self, client):
        """Precondition for the two tests above. If the client ever starts setting
        Content-Length, they would silently stop covering this path and merely
        re-test the header check a second time."""
        request = client.build_request("POST", "/echo", content=self._chunks(LIMIT * 6))
        assert not any(k.lower() == "content-length" for k in request.headers)

    def test_only_one_response_is_produced(self, client):
        """A regression guard for the actual bug in the first implementation.

        Rejecting from the receive side while the app is still going to respond
        sent two `http.response.start` messages. Starlette does not discard the
        second — httpx asserted `not response_started` and the request blew up
        rather than returning 413. A single clean 413 here IS that assertion.
        """
        resp = client.post("/echo", content=self._chunks(LIMIT * 6))
        assert resp.status_code == 413
        assert json.loads(resp.text)["errorCode"] == "REQUEST_BODY_TOO_LARGE"


class TestWhatIsDeliberatelyNotChecked:
    def test_zero_disables_enforcement(self):
        client = TestClient(_build_app(max_bytes=0))
        resp = client.post("/echo", content=b"x" * (LIMIT * 100))
        assert resp.status_code == 200, (
            "max_bytes=0 must disable the limit — it is the documented escape "
            "hatch for deployments where a reverse proxy already bounds bodies"
        )

    def test_a_get_without_a_body_is_unaffected(self, client):
        assert client.get("/echo").status_code == 200

    @pytest.mark.parametrize("method", ["POST", "PUT", "DELETE"])
    def test_every_body_carrying_method_is_bounded(self, method):
        """No method is exempt.

        An earlier version skipped GET/HEAD/OPTIONS/DELETE/TRACE as "bodyless" to
        keep two closures off the hot path. DELETE and OPTIONS may legally carry a
        body, and a probe confirmed the hole: `DELETE` with an 8 KB body returned
        200 and the handler read all 8192 bytes. The optimisation is gone; the
        wrapper costs two closures per request.
        """

        async def echo(request: Request) -> JSONResponse:
            return JSONResponse({"read": len(await request.body())})

        app = Starlette(routes=[Route("/m", echo, methods=[method])])
        app.add_middleware(BodySizeLimitMiddleware, max_bytes=LIMIT)

        resp = TestClient(app).request(method, "/m", content=b"x" * (LIMIT * 8))
        assert resp.status_code == 413

    def test_a_malformed_content_length_falls_back_to_counting(self):
        """A bogus header must not be usable to skip the limit. Sent at the raw
        ASGI level because an HTTP client will not emit an invalid header."""
        import anyio

        app = _build_app()
        stack = app.build_middleware_stack()
        sent: list[dict] = []
        chunks = [b"x" * 512, b"x" * 512, b"x" * 512]

        async def receive():
            if chunks:
                return {
                    "type": "http.request",
                    "body": chunks.pop(0),
                    "more_body": bool(chunks),
                }
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(message):
            sent.append(message)

        scope = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "POST",
            "path": "/echo",
            "raw_path": b"/echo",
            "query_string": b"",
            "root_path": "",
            "scheme": "http",
            "headers": [(b"content-length", b"not-a-number")],
            "client": ("127.0.0.1", 1234),
            "server": ("testserver", 80),
        }
        anyio.run(stack, scope, receive, send)

        start = next(m for m in sent if m["type"] == "http.response.start")
        assert start["status"] == 413, (
            "a malformed Content-Length let an oversized body through"
        )


class TestTheExceptionGuardIsNarrow:
    """The reject path swallows the app's unwind exception. That suppression must
    apply ONLY after a rejection, or the middleware would hide every real error
    behind a 200-shaped silence."""

    def test_an_app_error_still_propagates_when_nothing_was_rejected(self):
        async def boom(request: Request) -> JSONResponse:
            raise RuntimeError("deliberate")

        app = Starlette(routes=[Route("/boom", boom, methods=["POST"])])
        app.add_middleware(BodySizeLimitMiddleware, max_bytes=LIMIT)

        with pytest.raises(RuntimeError, match="deliberate"):
            TestClient(app, raise_server_exceptions=True).post("/boom", content=b"ok")

    def test_an_app_error_on_a_small_body_is_not_turned_into_a_413(self):
        async def boom(request: Request) -> JSONResponse:
            await request.body()
            raise RuntimeError("deliberate")

        app = Starlette(routes=[Route("/boom", boom, methods=["POST"])])
        app.add_middleware(BodySizeLimitMiddleware, max_bytes=LIMIT)

        resp = TestClient(app, raise_server_exceptions=False).post(
            "/boom", content=b"x" * (LIMIT - 1)
        )
        assert resp.status_code == 500, (
            "a genuine handler error was masked; the exception guard is only "
            "meant to apply once a 413 has already been sent"
        )


class TestEnforcementStopsOnceTheAppHasCommittedAResponse:
    """The design that replaced three failed attempts at acting mid-response.

    An app may begin responding while still reading — legal ASGI. Three earlier
    versions each tried to *do* something when the limit tripped after that point,
    and each was wrong:

      1. Drop the app's frames  -> response never terminates (headers, no body).
      2. Forward them           -> no termination guarantee at all.
      3. Synthesize an empty terminal frame -> corrupts any response that declared
         a `content-length`. h11: "Too little data for declared Content-Length".

    Four of this module's six review findings came out of that subtree, including
    all three rounds where fixing one hole opened another. It is now deleted: once
    `http.response.start` is on the wire the middleware logs and stops enforcing.

    The reasoning, not just the retreat: the threat this middleware exists to stop
    is FastAPI parsing a body before auth can reject it. Once the app has produced
    a response it has already got what it needed from the body, so the threat is
    past by definition. And no shipped route can reach this path — there is no
    `StreamingResponse`, `FileResponse` or `request.stream()` anywhere in `src/` or
    `examples/`, verified by grep.

    The trade, stated rather than hidden: a streaming proxy endpoint would be
    unbounded after it commits. That endpoint does not exist here, and an ingress
    limit covers it if it ever does.
    """

    @staticmethod
    def _app(*, declare_length: bool, raises_on_disconnect: bool):
        async def app(scope, receive, send):
            headers = [(b"content-type", b"text/plain")]
            if declare_length:
                headers.append((b"content-length", b"12"))
            await send(
                {"type": "http.response.start", "status": 200, "headers": headers}
            )
            while True:
                message = await receive()
                if message["type"] == "http.disconnect":
                    if raises_on_disconnect:
                        # What a real Starlette streaming endpoint does:
                        # `Request.stream()` turns the disconnect into
                        # ClientDisconnect. Every disconnect-handling app in the
                        # first five rounds of this file used `break` instead,
                        # which is precisely why the exception-latch defect
                        # survived all of them.
                        from starlette.requests import ClientDisconnect

                        raise ClientDisconnect()
                    break
                if not message.get("more_body", False):
                    break
            for index in range(3):
                await send(
                    {
                        "type": "http.response.body",
                        "body": b"data",
                        "more_body": index < 2,
                    }
                )

        return app

    def _run(self, app) -> tuple[list[dict], str | None]:
        import anyio

        middleware = BodySizeLimitMiddleware(app, max_bytes=LIMIT)
        sent: list[dict] = []
        chunks = [b"x" * 600] * 5

        async def receive():
            if chunks:
                return {
                    "type": "http.request",
                    "body": chunks.pop(0),
                    "more_body": bool(chunks),
                }
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(message):
            sent.append(message)

        escaped: str | None = None
        try:
            anyio.run(middleware, _raw_scope(), receive, send)
        except BaseException as exc:  # noqa: BLE001 - recorded, not handled
            escaped = type(exc).__name__
        return sent, escaped

    @pytest.mark.parametrize(
        "declare_length", [False, True], ids=["no-length", "declared-length"]
    )
    @pytest.mark.parametrize(
        "raises_on_disconnect", [False, True], ids=["breaks", "raises"]
    )
    def test_the_app_response_completes_untouched(
        self, declare_length, raises_on_disconnect
    ):
        sent, escaped = self._run(
            self._app(
                declare_length=declare_length,
                raises_on_disconnect=raises_on_disconnect,
            )
        )

        starts = [m for m in sent if m["type"] == "http.response.start"]
        assert len(starts) == 1, f"{len(starts)} response starts; ASGI allows one"
        assert starts[0]["status"] == 200, "the app's status was overwritten"

        bodies = [m for m in sent if m["type"] == "http.response.body"]
        assert b"".join(m["body"] for m in bodies) == b"data" * 3, (
            "the app's response was truncated; enforcement should have stopped, "
            "not interfered with a response already in flight"
        )
        assert bodies[-1].get("more_body", False) is False

        assert escaped is None, (
            f"{escaped} escaped for a request the middleware chose not to reject. "
            "Starlette's error middleware would turn that into an ERROR-level "
            "unhandled_exception AND a false 500 notification dispatch"
        )

    def test_the_emitted_sequence_is_valid_to_h11(self):
        """Counting frames cannot catch a length mismatch; h11 can. Replays both
        length variants through the parser uvicorn uses."""
        import h11

        for declare_length in (False, True):
            sent, _ = self._run(
                self._app(declare_length=declare_length, raises_on_disconnect=True)
            )
            conn = h11.Connection(our_role=h11.SERVER)
            conn.receive_data(
                b"POST / HTTP/1.1\r\nHost: t\r\nContent-Length: 5\r\n\r\nhello"
            )
            conn.next_event()
            conn.next_event()
            start = next(m for m in sent if m["type"] == "http.response.start")
            conn.send(
                h11.Response(
                    status_code=start["status"],
                    headers=[(k, v) for k, v in start["headers"]],
                )
            )
            for message in sent:
                if message["type"] != "http.response.body":
                    continue
                if message["body"]:
                    conn.send(h11.Data(data=message["body"]))
                if not message.get("more_body", False):
                    conn.send(h11.EndOfMessage())

    def test_the_decision_is_logged(self):
        """Silently going unbounded would be the worst version of this. The
        operator gets a record naming the limit and how much arrived."""
        from structlog.testing import capture_logs

        with capture_logs() as logs:
            self._run(self._app(declare_length=False, raises_on_disconnect=False))
        events = [r.get("event") for r in logs]
        assert "request_body_too_large_after_response_started" in events, events


class TestARealRejectionStillWorks:
    """The path that matters, kept adjacent so the retreat above cannot quietly
    widen into "never reject anything"."""

    def test_a_body_over_the_limit_before_any_response_is_still_413(self, client):
        assert client.post("/echo", content=b"x" * (LIMIT * 4)).status_code == 413
