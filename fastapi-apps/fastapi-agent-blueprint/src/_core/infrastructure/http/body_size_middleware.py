"""Reject oversized request bodies before the app parses them (#322).

Nothing bounded request bodies. FastAPI reads and JSON-parses the whole body
before validation — or even authentication — can reject it, so an unauthenticated
caller could make the process allocate and parse an arbitrarily large document.
Measured against `POST /v1/user`, which requires an admin token:

    1MB  -> 401 in 0.05s
    16MB -> 401 in 0.07s
    64MB -> 401 in 0.28s      <- the body was read before the 401

The collection bounds from the same issue cap how much *work* a valid body can
trigger (`Field(max_length=100)` on the batch endpoints). This caps the
cumulative request bytes delivered past this middleware to route parsing, for
an app that consumes the ASGI receive stream. It is not a bound on what the
HTTP server buffers before this middleware is invoked.

Two enforcement points, and the second is the one that matters
--------------------------------------------------------------
A `Content-Length` check alone is not a control: HTTP/1.1 chunked transfer
encoding sends no `Content-Length`, and a caller who omits it skips a
header-only check entirely. Verified that httpx builds exactly such a request
against this app:

    64MB (chunked) -> Content-Length present: False

So this middleware also counts bytes as they stream and aborts mid-body. The
header check is kept because it is free and fails fast — before any of the body
is delivered to the wrapped app, though not before the HTTP server has accepted
it off the socket, which is not this middleware's to control.

What this does NOT guarantee
---------------------------
Three gaps, all measured, all deliberate, and they are not equivalent. The first
two never deliver the body to route parsing, so they do not re-introduce the
parse-cost problem above. The third does deliver it — deliberately, because by
then the app has already produced a response and the parse has already happened.
None of them bounds buffering the HTTP server may have done before this middleware
runs. A claim of "every request is bounded" would be false, so:

- **The byte counter only runs when the app calls ``receive()``.** An endpoint
  that returns without reading the body is not bounded by it (the header check
  still applies — though a chunked caller carries no header for it to check). This middleware never calls ``receive()`` on that path, so
  the bytes are never delivered to the application — what the protocol server
  does with them is outside this middleware's control.
- **A CORS preflight never reaches this middleware.** ``CORSMiddleware`` sits
  outside it and answers ``OPTIONS`` + ``Access-Control-Request-Method`` itself.
  Measured against the shipped order: preflight with an 11-byte body against a
  10-byte limit returns 200, while a non-preflight ``OPTIONS`` returns 413. The
  placement is still the right trade: moving this middleware outside CORS would
  bound preflight bodies nobody reads, at the cost of the 413 losing the CORS
  headers a browser needs in order to read it.

- **A response already begun is never turned into a 413.** If the app sent its
  ``http.response.start`` before the limit tripped, the status is not ours to set:
  the counter logs ``request_body_too_large_after_response_started`` and **stops
  enforcing** for that request, letting the response the app committed complete
  untouched. Accepted because the threat this middleware exists to stop — a body
  parsed before auth can reject it — is already past once the app has produced a
  response, and because no shipped route can reach it: there is no
  ``StreamingResponse``, ``FileResponse`` or ``request.stream()`` anywhere in
  ``src/`` or ``examples/``. The trade is that a streaming proxy endpoint would be
  unbounded after it commits; an ingress limit covers that.

  Three earlier versions tried to *act* here instead — drop the app's frames
  (response never terminates), forward them (no termination guarantee), synthesize
  an empty terminal frame (corrupts a declared ``content-length``; h11 raises
  "Too little data for declared Content-Length"). Four of this module's six review
  findings came from that subtree. Do not reintroduce it without a route that
  needs it.

If a deployment needs "no request over N bytes reaches the process at all", that
belongs at the ingress proxy. Note also that a 413 does not close the connection,
so a conforming server drains the rejected body before reusing it — the bytes still
cross the wire. ``Connection: close`` on the 413 is the nginx behaviour and a
defensible hardening; it is not done here because it costs a legitimate client its
keep-alive and risks RST-truncating the 413 body off-loopback. This middleware does not bound ingress or
protocol-server buffering, nor an individual ASGI frame already materialised
before it observes it.
"""

from __future__ import annotations

import structlog
from starlette.datastructures import Headers
from starlette.types import ASGIApp, Message, Receive, Scope, Send

_logger = structlog.stdlib.get_logger(__name__)

_HTTP_REQUEST_ENTITY_TOO_LARGE = 413


class _RejectionState:
    """Shared between the wrapped ``receive`` and ``send`` for one request."""

    __slots__ = (
        "enforcement_stopped",
        "received",
        "rejected",
        "rejection_sent",
        "response_started",
    )

    def __init__(self) -> None:
        self.received = 0
        # Set once a 413 has been *sent*. Licenses dropping the app's late
        # response and swallowing the unwind exception the truncated body causes.
        self.rejected = False
        # Set only after `_reject` finished writing. If it fails partway the
        # response is not on the wire, so the exception must keep propagating.
        self.rejection_sent = False
        self.response_started = False
        # Set when the limit is crossed *after* the app committed a response. At
        # that point the status is not ours to set, so enforcement stops rather
        # than trying to alter a response already in flight — see `__call__`.
        self.enforcement_stopped = False


class BodySizeLimitMiddleware:
    """Pure-ASGI middleware bounding the request body.

    Deliberately not a ``BaseHTTPMiddleware`` subclass: that base buffers the
    whole request into a ``Request`` object to hand a body to the endpoint, which
    is the exact allocation this exists to prevent. Working at the ASGI level lets
    the byte counter run against the raw ``receive`` stream and stop it partway.
    """

    def __init__(self, app: ASGIApp, *, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or self.max_bytes <= 0:
            await self.app(scope, receive, send)
            return

        state = _RejectionState()
        declared = self._declared_length(scope)
        if declared is not None and declared > self.max_bytes:
            await self._reject(
                scope, send, declared=declared, received=None, state=state
            )
            return

        # Both sides are wrapped. Rejecting mid-stream means responding from the
        # receive side while the app still intends to respond, and an ASGI server
        # rejects the second `http.response.start` — httpx's transport fails on
        # `assert not response_started`, and uvicorn raises "Unexpected message".
        # Guarding `send` is what actually makes "the app's response is
        # discarded" true; an earlier version only claimed it and crashed.
        try:
            await self.app(
                scope,
                self._counting_receive(scope, send, receive, state),
                self._guarded_send(send, state),
            )
        except Exception:
            # Only after we have already responded. Cutting the body off makes the
            # app unwind — Starlette turns our `http.disconnect` into
            # `ClientDisconnect` inside `await request.body()` — and that
            # exception has nowhere useful to go: the 413 is on the wire, so
            # letting it propagate would surface as a server error for a request
            # that was correctly rejected. If we have NOT rejected, the exception
            # is a real one and must keep propagating.
            if not state.rejection_sent:
                raise

    def _declared_length(self, scope: Scope) -> int | None:
        raw = Headers(scope=scope).get("content-length")
        if raw is None:
            return None
        try:
            return int(raw)
        except ValueError:
            # A malformed Content-Length is not ours to adjudicate; the protocol
            # layer or the app will reject it. Fall through to byte counting so a
            # bogus header cannot be used to skip the limit.
            return None

    def _counting_receive(
        self, scope: Scope, send: Send, receive: Receive, state: _RejectionState
    ) -> Receive:
        async def counting_receive() -> Message:
            if state.rejected:
                # A 413 is on the wire. Keep telling the app the client is gone so
                # it unwinds instead of blocking on a stream we stopped serving.
                return {"type": "http.disconnect"}

            message = await receive()
            if message["type"] != "http.request" or state.enforcement_stopped:
                return message

            state.received += len(message.get("body", b""))
            if state.received <= self.max_bytes:
                return message

            if state.response_started:
                # The app already committed a response, so the status is no longer
                # ours and the parse-cost this middleware exists to prevent is
                # already past — the app produced a response, so it got what it
                # needed from the body. Log it and get out of the way.
                #
                # Three earlier attempts tried to *act* here and each was wrong.
                # Dropping the app's frames left the response unterminated.
                # Forwarding them gave no termination guarantee. Synthesizing an
                # empty terminal frame corrupted any response that declared a
                # `content-length` — h11: "Too little data for declared
                # Content-Length". Four of this module's six review findings came
                # from that subtree, and no shipped route can even reach it: there
                # is no `StreamingResponse`, `FileResponse` or `request.stream()`
                # anywhere in `src/` or `examples/`.
                state.enforcement_stopped = True
                _logger.warning(
                    "request_body_too_large_after_response_started",
                    http_method=scope.get("method"),
                    http_path=scope.get("path"),
                    limit_bytes=self.max_bytes,
                    received_bytes=state.received,
                )
                return message

            state.rejected = True
            await self._reject(
                scope, send, declared=None, received=state.received, state=state
            )
            return {"type": "http.disconnect"}

        return counting_receive

    def _guarded_send(self, send: Send, state: _RejectionState) -> Send:
        async def guarded_send(message: Message) -> None:
            if state.rejected:
                # The 413 is the response. Whatever the app produces from a
                # truncated body — a 422, a 500 — must not become a second one.
                return
            if message["type"] == "http.response.start":
                state.response_started = True
            await send(message)

        return guarded_send

    async def _reject(
        self,
        scope: Scope,
        send: Send,
        *,
        declared: int | None,
        received: int | None,
        state: _RejectionState,
    ) -> None:
        _logger.warning(
            "request_body_too_large",
            http_method=scope.get("method"),
            http_path=scope.get("path"),
            limit_bytes=self.max_bytes,
            declared_bytes=declared,
            received_bytes=received,
        )
        # Hand-rolled rather than a JSONResponse: this runs outside the exception
        # handlers, and the payload deliberately mirrors ``ErrorResponse`` so a
        # client parses a 413 the same way it parses every other error. The limit
        # is included because it is configuration, not internal detail.
        body = (
            b'{"success":false,'
            b'"message":"Request body exceeds the maximum of '
            + str(self.max_bytes).encode()
            + b' bytes",'
            b'"errorCode":"REQUEST_BODY_TOO_LARGE",'
            b'"errorDetails":null}'
        )
        await send(
            {
                "type": "http.response.start",
                "status": _HTTP_REQUEST_ENTITY_TOO_LARGE,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body, "more_body": False})
        state.rejection_sent = True
