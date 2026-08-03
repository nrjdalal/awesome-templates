import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import aiohttp
import structlog

from src._core.infrastructure.http.exceptions import (
    ExternalServiceException,
    ExternalServiceTimeoutException,
)

_logger = structlog.stdlib.get_logger(__name__)

_DEFAULT_PORTS = frozenset({80, 443})


def _safe_origin(exc: aiohttp.ClientError) -> str | None:
    """``scheme://host[:port]`` for the failed request — path and query dropped.

    The path is the secret half of a webhook URL (a Slack token lives in
    ``/services/T/B/X``); the origin is not. Keeping the origin makes the log
    actionable without re-introducing the leak that ``error_notifier.py`` avoids
    deliberately: both webhook adapters POST through this client, so anything
    logged here can be a credential.

    Returns ``None`` for the errors that carry no request context at all
    (``ClientPayloadError`` has neither ``request_info`` nor ``host``).
    """
    request_info = getattr(exc, "request_info", None)
    url = getattr(request_info, "url", None)
    if url is not None:
        suffix = f":{url.port}" if url.port not in _DEFAULT_PORTS else ""
        return f"{url.scheme}://{url.host}{suffix}"

    # ClientConnectorError never got a response, so it exposes host/port instead.
    host = getattr(exc, "host", None)
    if host is not None:
        port = getattr(exc, "port", None)
        if port is None or port in _DEFAULT_PORTS:
            return str(host)
        return f"{host}:{port}"

    return None


def _curate_client_error(exc: aiohttp.ClientError) -> ExternalServiceException:
    """Build the 502 for an aiohttp failure without copying its message.

    ``f"External service error: {exc}"`` published request detail to the caller:
    ``ClientResponseError`` renders the **full URL** and ``ClientConnectorError``
    the internal ``host:port``. Verified on aiohttp 3.13.5::

        403, message='Forbidden', url='https://hooks.slack.com/services/T/B/X'
        Cannot connect to host internal-svc.prod:8443 ssl:default [None]

    ``security-checklist.md`` §13 records that property for the log stream; it
    applies just as much to a response body. The client now gets the failure
    class and the upstream status; the origin goes to the log only.
    """
    status = getattr(exc, "status", None)
    _logger.error(
        "external_service_error",
        exc_type=type(exc).__name__,
        upstream_status=status,
        origin=_safe_origin(exc),
    )
    detail = f"{type(exc).__name__}"
    if status is not None:
        detail = f"{detail} {status}"
    return ExternalServiceException(message=f"External service error [{detail}]")


def get_http_client_config(env: str):
    if env == "prod":
        return {
            "timeout": aiohttp.ClientTimeout(total=30, connect=10, sock_read=30),
            "connector_kwargs": {
                "limit": 100,
                "limit_per_host": 30,
                "ttl_dns_cache": 300,
                "keepalive_timeout": 30,
            },
        }
    else:
        return {
            "timeout": aiohttp.ClientTimeout(total=10, connect=5, sock_read=10),
            "connector_kwargs": {
                "limit": 50,
                "limit_per_host": 20,
                "ttl_dns_cache": 300,
            },
        }


class HttpClient:
    def __init__(self, env: str) -> None:
        self.env = env
        self._config = get_http_client_config(env=env)
        self._client_session: aiohttp.ClientSession | None = None
        self._session_loop: asyncio.AbstractEventLoop | None = None

    async def _ensure_session(self) -> aiohttp.ClientSession:
        # Check the currently running event loop
        try:
            current_loop = asyncio.get_running_loop()
            if self._client_session and self._session_loop != current_loop:
                # Reset session if the event loop has changed or closed
                self._client_session = None
                self._session_loop = None
        except RuntimeError:
            # No running loop (e.g. synchronous context) - ignore and create new
            pass

        if self._client_session is None or self._client_session.closed:
            connector = aiohttp.TCPConnector(**self._config["connector_kwargs"])
            self._client_session = aiohttp.ClientSession(
                timeout=self._config["timeout"],
                connector=connector,
            )
            try:
                self._session_loop = asyncio.get_running_loop()
            except RuntimeError:
                self._session_loop = None
        return self._client_session

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[aiohttp.ClientSession, None]:
        session = None

        try:
            session = await self._ensure_session()
            yield session
        # Order is load-bearing: on aiohttp 3.13.5 every timeout class
        # (ServerTimeoutError, SocketTimeoutError, ConnectionTimeoutError)
        # subclasses *both* TimeoutError and aiohttp.ClientError, so catching
        # ClientError first made the 504 branch unreachable for all three — a
        # timed-out upstream was reported as a 502.
        except TimeoutError as e:
            _logger.error(
                "external_service_timeout",
                exc_type=type(e).__name__,
                origin=_safe_origin(e) if isinstance(e, aiohttp.ClientError) else None,
            )
            raise ExternalServiceTimeoutException() from e
        except aiohttp.ClientError as e:
            raise _curate_client_error(e) from e

    async def dispose(self) -> None:
        if self._client_session and not self._client_session.closed:
            await self._client_session.close()
            self._client_session = None
