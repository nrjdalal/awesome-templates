from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from aioboto3 import Session
    from types_aiobotocore_s3.client import S3Client as BotoS3Client


_AWS_EXTRA_HINT = (
    "Missing optional dependency 'aioboto3' for object storage (S3/MinIO). "
    "Install with: uv sync --extra aws"
)


class ObjectStorageClient:
    def __init__(
        self,
        access_key: str,
        secret_access_key: str,
        region_name: str = "ap-northeast-2",
        endpoint_url: str | None = None,
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
        self.endpoint_url = endpoint_url

    @asynccontextmanager
    async def client(self) -> AsyncGenerator[BotoS3Client, None]:
        async with self.session.client(
            "s3", endpoint_url=self.endpoint_url
        ) as s3_client:
            yield s3_client
