from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

import structlog

_logger = structlog.stdlib.get_logger(__name__)

from src._core.infrastructure.vectors.s3.exceptions import (
    S3VectorException,
    S3VectorIndexNotFoundException,
    S3VectorThrottlingException,
)

if TYPE_CHECKING:
    from aioboto3 import Session
    from botocore.exceptions import ClientError
    from types_aiobotocore_s3vectors.client import S3VectorsClient
else:
    try:
        from botocore.exceptions import ClientError
    except ImportError:
        # ``[aws]`` extra not installed. ``S3VectorClient.__init__`` raises
        # ImportError with the install hint, so this fallback never catches
        # a real exception.
        class ClientError(Exception):
            pass


_AWS_EXTRA_HINT = (
    "Missing optional dependency 'aioboto3' for S3 Vectors support. "
    "Install with: uv sync --extra aws"
)


class S3VectorClient:
    """Async S3 Vectors client wrapper using aioboto3.

    Pattern identical to ``DynamoDBClient``:
    - Session held as instance attribute (Singleton in DI)
    - Client created per operation via async context manager
    - ``ClientError`` wrapped into domain exceptions at client level
    - Errors only occur when ``client()`` is actually called, not at init
      (allows Singleton creation with ``None`` config when S3 Vectors not used)
    """

    def __init__(
        self,
        access_key: str,
        secret_access_key: str,
        region_name: str = "us-east-2",
    ) -> None:
        try:
            import aioboto3
        except ImportError as exc:
            raise ImportError(_AWS_EXTRA_HINT) from exc

        self.session: Session = aioboto3.Session(
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_access_key,
            region_name=region_name,
        )

    # Yields the service-specific ``S3VectorsClient``, not the generic
    # ``AioBaseClient`` this used to declare. aiobotocore builds each client as a
    # dynamic subclass whose API methods are set as real attributes, so the base
    # class carries none of them — and its ``__getattr__`` unconditionally raises
    # AttributeError, which a type checker reads as ``NoReturn``. Under the old
    # annotation every ``await client.put_vectors(...)`` in ``BaseS3VectorStore``
    # therefore reported "NoReturn is not awaitable", and none of the four
    # s3vectors calls was ever checked. Same pattern as ``DynamoDBClient``.
    @asynccontextmanager
    async def client(self) -> AsyncGenerator[S3VectorsClient, None]:
        try:
            async with self.session.client("s3vectors") as s3v_client:
                yield s3v_client
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")

            if error_code == "NotFoundException":
                raise S3VectorIndexNotFoundException() from e
            if error_code == "TooManyRequestsException":
                raise S3VectorThrottlingException() from e

            # The provider message is deliberately NOT a structlog kwarg:
            # security-checklist.md:194 requires kwargs carry no sensitive
            # fields, and an AWS `Error.Message` names the calling IAM principal
            # ARN (embedding the account id) plus the table/bucket/key. The
            # `from e` chain below still carries the full text, which is where
            # `custom_exception_handler` renders it via `exc_info` — the log is
            # the one sink that is allowed to have it.
            _logger.error(
                "s3vectors_operation_failed",
                error_code=error_code,
                provider_exception_type=type(e).__name__,
            )
            raise S3VectorException(
                status_code=500,
                message=f"S3 Vectors operation failed [{error_code}]",
                error_code="S3VECTOR_OPERATION_FAILED",
            ) from e
