from __future__ import annotations

from io import BytesIO
from typing import TYPE_CHECKING, BinaryIO

import structlog

from src._core.exceptions.base_exception import BaseCustomException
from src._core.infrastructure.storage.object_storage_client import ObjectStorageClient

_logger = structlog.stdlib.get_logger(__name__)

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


def _error_code(exc: ClientError) -> str:
    """``Error.Code`` off a botocore error, tolerating a malformed response.

    ``.get()`` rather than ``e.response["Error"]["Code"]``: the subscript form
    used here previously raises ``KeyError`` inside an ``except`` block for any
    error whose response lacks the key, replacing the real storage failure with
    an unrelated traceback. Mirrors ``dynamodb_client.py``.
    """
    response = getattr(exc, "response", None) or {}
    return response.get("Error", {}).get("Code", "Unknown")


def _storage_failure(operation: str, exc: ClientError) -> BaseCustomException:
    """Curate a botocore storage error into a 500 that omits its message.

    ``f"Storage {op} failed: {e}"`` copied the provider text into the response
    body. A boto3 ``AccessDenied`` message names the calling IAM principal ARN
    (which embeds the 12-digit AWS account id), the bucket and the key::

        An error occurred (AccessDenied) when calling the PutObject operation:
        User: arn:aws:sts::123456789012:assumed-role/app-runtime/session is not
        authorized to perform: s3:PutObject on resource: arn:aws:s3:::bucket/key

    The client now gets the operation and the error code; the provider message
    goes to the log. Same split as ``dynamodb_client.py`` and
    ``vectors/s3/client.py``, which are the house pattern for this.
    """
    code = _error_code(exc)
    # The provider message is deliberately NOT a structlog kwarg — see the note
    # in dynamodb_client.py. An S3 `Error.Message` is the worst case of the
    # family: besides the IAM principal ARN and account id it names the object
    # key, which for a user-uploaded file is often itself personal data. The
    # `from e` chain still carries the text for `exc_info` rendering.
    _logger.error(
        "storage_operation_failed",
        operation=operation,
        error_code=code,
        provider_exception_type=type(exc).__name__,
    )
    return BaseCustomException(
        status_code=500,
        message=f"Storage {operation} failed [{code}]",
        error_code="STORAGE_OPERATION_FAILED",
    )


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
            raise _storage_failure("upload", e) from e

    async def download_file(self, key: str) -> bytes:
        """Download a file."""
        try:
            async with self.storage_client.client() as client:
                response = await client.get_object(Bucket=self.bucket_name, Key=key)
                async with response["Body"] as stream:
                    return await stream.read()
        except ClientError as e:
            if _error_code(e) == "NoSuchKey":
                raise BaseCustomException(
                    status_code=404,
                    message=f"File not found: {key}",
                    error_code="STORAGE_FILE_NOT_FOUND",
                ) from e
            raise _storage_failure("download", e) from e

    async def delete_file(self, key: str) -> bool:
        """Delete a file."""
        try:
            async with self.storage_client.client() as client:
                await client.delete_object(Bucket=self.bucket_name, Key=key)
                return True
        except ClientError as e:
            raise _storage_failure("delete", e) from e

    async def file_exists(self, key: str) -> bool:
        """Check whether a file exists."""
        try:
            async with self.storage_client.client() as client:
                await client.head_object(Bucket=self.bucket_name, Key=key)
                return True
        except ClientError as e:
            # "404" and not "NoSuchKey": HEAD has no response body, so botocore
            # falls back to the HTTP status as the error code. Unchanged from
            # before — only the extraction is now KeyError-safe.
            if _error_code(e) == "404":
                return False
            raise _storage_failure("check", e) from e

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
            raise _storage_failure("presigned URL generation", e) from e

    async def list_files(self, prefix: str = "") -> list[str]:
        """List files."""
        try:
            async with self.storage_client.client() as client:
                response = await client.list_objects_v2(
                    Bucket=self.bucket_name, Prefix=prefix
                )
                if "Contents" not in response:
                    return []
                # `Key` is optional in the S3 response model, so the direct
                # subscript was an unguarded KeyError. Real S3 always sends it;
                # skipping a keyless entry is still the right fallback, because
                # this method's contract is "keys you can address" and an empty
                # string would be handed straight to a download or delete call.
                return [key for obj in response["Contents"] if (key := obj.get("Key"))]
        except ClientError as e:
            raise _storage_failure("list", e) from e
