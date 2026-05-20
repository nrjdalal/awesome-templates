from __future__ import annotations

from io import BytesIO
from typing import TYPE_CHECKING, BinaryIO

from src._core.exceptions.base_exception import BaseCustomException
from src._core.infrastructure.storage.object_storage_client import ObjectStorageClient

if TYPE_CHECKING:
    from botocore.exceptions import ClientError
else:
    try:
        from botocore.exceptions import ClientError
    except ImportError:
        # ``botocore`` ships with ``boto3`` / ``aioboto3`` (both in the
        # ``[aws]`` extra). When it is not installed, this module still
        # imports cleanly so the app boots. Any real ``ObjectStorage``
        # call path goes through ``ObjectStorageClient`` which raises an
        # ImportError at construction time pointing at ``uv sync --extra aws``
        # — so this fallback never actually catches an exception.
        class ClientError(Exception):
            pass


class ObjectStorage:
    def __init__(self, storage_client: ObjectStorageClient, bucket_name: str) -> None:
        self.storage_client = storage_client
        self.bucket_name = bucket_name

    async def upload_file(
        self,
        file_obj: BinaryIO | bytes,
        key: str,
        content_type: str = "application/octet-stream",
    ) -> str:
        """Upload a file."""
        try:
            async with self.storage_client.client() as client:
                if isinstance(file_obj, bytes):
                    file_obj = BytesIO(file_obj)

                await client.upload_fileobj(
                    Fileobj=file_obj,
                    Bucket=self.bucket_name,
                    Key=key,
                    ExtraArgs={
                        "ContentType": content_type,
                        "ServerSideEncryption": "AES256",
                    },
                )
                return key
        except ClientError as e:
            raise BaseCustomException(
                status_code=500, message=f"Storage upload failed: {e}"
            )

    async def download_file(self, key: str) -> bytes:
        """Download a file."""
        try:
            async with self.storage_client.client() as client:
                response = await client.get_object(Bucket=self.bucket_name, Key=key)
                async with response["Body"] as stream:
                    return await stream.read()
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                raise BaseCustomException(
                    status_code=404, message=f"File not found: {key}"
                )
            raise BaseCustomException(
                status_code=500, message=f"Storage download failed: {e}"
            )

    async def delete_file(self, key: str) -> bool:
        """Delete a file."""
        try:
            async with self.storage_client.client() as client:
                await client.delete_object(Bucket=self.bucket_name, Key=key)
                return True
        except ClientError as e:
            raise BaseCustomException(
                status_code=500, message=f"Storage delete failed: {e}"
            )

    async def file_exists(self, key: str) -> bool:
        """Check whether a file exists."""
        try:
            async with self.storage_client.client() as client:
                await client.head_object(Bucket=self.bucket_name, Key=key)
                return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                return False
            raise BaseCustomException(
                status_code=500, message=f"Storage check failed: {e}"
            )

    async def get_file_url(self, key: str, expires_in: int = 3600) -> str:
        """Generate a presigned URL for a file."""
        try:
            async with self.storage_client.client() as client:
                url = await client.generate_presigned_url(
                    "get_object",
                    Params={"Bucket": self.bucket_name, "Key": key},
                    ExpiresIn=expires_in,
                )
                return url
        except ClientError as e:
            raise BaseCustomException(
                status_code=500, message=f"Storage presigned URL generation failed: {e}"
            )

    async def list_files(self, prefix: str = "") -> list[str]:
        """List files."""
        try:
            async with self.storage_client.client() as client:
                response = await client.list_objects_v2(
                    Bucket=self.bucket_name, Prefix=prefix
                )
                if "Contents" not in response:
                    return []
                return [obj["Key"] for obj in response["Contents"]]
        except ClientError as e:
            raise BaseCustomException(
                status_code=500, message=f"Storage list failed: {e}"
            )
