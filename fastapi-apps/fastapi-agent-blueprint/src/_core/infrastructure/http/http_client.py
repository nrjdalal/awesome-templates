import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import aiohttp

from src._core.infrastructure.http.exceptions import (
    ExternalServiceException,
    ExternalServiceTimeoutException,
)


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
        except aiohttp.ClientError as e:
            raise ExternalServiceException(message=f"External service error: {e}")
        except TimeoutError:
            raise ExternalServiceTimeoutException()

    async def dispose(self) -> None:
        if self._client_session and not self._client_session.closed:
            await self._client_session.close()
            self._client_session = None
