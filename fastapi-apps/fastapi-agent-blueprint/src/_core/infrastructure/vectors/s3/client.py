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
    from aiobotocore.client import AioBaseClient
    from botocore.exceptions import ClientError
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

    @asynccontextmanager
    async def client(self) -> AsyncGenerator[AioBaseClient, None]:
        try:
            async with self.session.client("s3vectors") as s3v_client:
                yield s3v_client
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            error_message = e.response.get("Error", {}).get("Message", str(e))

            if error_code == "NotFoundException":
                raise S3VectorIndexNotFoundException() from e
            if error_code == "TooManyRequestsException":
                raise S3VectorThrottlingException() from e

            _logger.error(
                "s3vectors_operation_failed",
                error_code=error_code,
                error_message=error_message,
            )
            raise S3VectorException(
                status_code=500,
                message=f"S3 Vectors operation failed [{error_code}]",
                error_code="S3VECTOR_OPERATION_FAILED",
            ) from e
