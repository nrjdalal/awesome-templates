"""Raw provider exception text must not reach a response body (#323).

`dynamodb_client.py:76-92` is the house pattern: pull `Error.Code` out, log the
raw provider message via structlog, and raise a curated exception carrying the
code but not the text. `vectors/s3/client.py` does the same.

Two modules did not. Both interpolate the provider exception straight into the
message a client receives:

- `object_storage.py` — all **six** `except ClientError` blocks. A boto3
  `AccessDenied` message names the calling IAM principal ARN (which embeds the
  12-digit account id), the bucket and the key.
- `http_client.py:73` — `f"External service error: {e}"`. Verified that
  aiohttp puts the full URL in `ClientResponseError` and the host:port in
  `ClientConnectorError`:

      403, message='Forbidden', url='https://hooks.slack.com/services/T/B/SECRET'
      Cannot connect to host internal-svc.prod:8443 ssl:default [None]

  `security-checklist.md` §13 already records that property for the log stream —
  it applies just as much to a response body, and for a notification webhook the
  URL *is* the credential.
"""

from __future__ import annotations

import aiohttp
import pytest
from botocore.exceptions import ClientError
from yarl import URL

from src._core.exceptions.base_exception import BaseCustomException

ACCOUNT = "123456789012"
ARN = f"arn:aws:sts::{ACCOUNT}:assumed-role/app-runtime/session"
BUCKET = "prod-customer-uploads"
KEY = "tenant-77/invoice-2026-08.pdf"
WEBHOOK = "https://hooks.slack.com/services/T/B/SECRET"


def _access_denied() -> ClientError:
    return ClientError(
        {
            "Error": {
                "Code": "AccessDenied",
                "Message": (
                    f"User: {ARN} is not authorized to perform: s3:PutObject "
                    f"on resource: arn:aws:s3:::{BUCKET}/{KEY}"
                ),
            }
        },
        "PutObject",
    )


class TestObjectStorageDoesNotLeakProviderText:
    """Every `except ClientError` in `object_storage.py`."""

    @pytest.fixture
    def storage(self):
        from src._core.infrastructure.storage.object_storage import ObjectStorage

        class _FailingClient:
            def client(self):
                raise _access_denied()

        return ObjectStorage(storage_client=_FailingClient(), bucket_name=BUCKET)

    @pytest.mark.parametrize(
        "call",
        [
            lambda s: s.upload_file(b"x", "k", "text/plain"),
            lambda s: s.download_file("k"),
            lambda s: s.delete_file("k"),
            lambda s: s.file_exists("k"),
            lambda s: s.get_file_url("k"),
            lambda s: s.list_files(),
        ],
        ids=["upload", "download", "delete", "exists", "presigned", "list"],
    )
    async def test_no_operation_leaks_the_arn_or_key(self, storage, call):
        with pytest.raises(BaseCustomException) as info:
            await call(storage)

        rendered = str(info.value) + str(info.value.message)
        for secret, label in (
            (ARN, "IAM principal ARN"),
            (ACCOUNT, "AWS account id"),
            (KEY, "object key"),
        ):
            assert secret not in rendered, (
                f"the {label} reached the client-visible message: {rendered!r}"
            )

    async def test_the_error_code_is_still_surfaced(self, storage):
        """Curating must not mean saying nothing — the operator needs the code."""
        with pytest.raises(BaseCustomException) as info:
            await storage.upload_file(b"x", "k", "text/plain")
        assert "AccessDenied" in str(info.value)

    async def test_missing_key_still_maps_to_404(self):
        """The pre-existing NoSuchKey branch must survive the curation change."""
        from src._core.infrastructure.storage.object_storage import ObjectStorage

        class _NoSuchKey:
            def client(self):
                raise ClientError(
                    {
                        "Error": {
                            "Code": "NoSuchKey",
                            "Message": "The key does not exist",
                        }
                    },
                    "GetObject",
                )

        storage = ObjectStorage(storage_client=_NoSuchKey(), bucket_name=BUCKET)
        with pytest.raises(BaseCustomException) as info:
            await storage.download_file("k")
        assert info.value.status_code == 404


class TestHttpClientDoesNotLeakTheOutboundUrl:
    def test_response_error_url_is_not_in_the_message(self):
        from src._core.infrastructure.http.exceptions import ExternalServiceException
        from src._core.infrastructure.http.http_client import _curate_client_error

        exc = aiohttp.ClientResponseError(
            request_info=aiohttp.RequestInfo(URL(WEBHOOK), "POST", {}, URL(WEBHOOK)),
            history=(),
            status=403,
            message="Forbidden",
        )
        assert WEBHOOK in str(exc), "precondition: aiohttp embeds the URL"

        curated = _curate_client_error(exc)
        assert isinstance(curated, ExternalServiceException)
        assert "hooks.slack.com" not in str(curated)
        assert "SECRET" not in str(curated)

    def test_connector_error_host_is_not_in_the_message(self):
        from src._core.infrastructure.http.http_client import _curate_client_error

        key = aiohttp.client_reqrep.ConnectionKey(
            "internal-svc.prod", 8443, False, True, None, None, None
        )
        exc = aiohttp.ClientConnectorError(key, OSError("refused"))
        assert "internal-svc" in str(exc), "precondition: aiohttp embeds the host"

        assert "internal-svc" not in str(_curate_client_error(exc))

    def test_the_exception_class_is_still_identifiable(self):
        from src._core.infrastructure.http.http_client import _curate_client_error

        curated = _curate_client_error(aiohttp.ClientPayloadError("truncated"))
        assert "ClientPayloadError" in str(curated)


class TestTimeoutStillMapsTo504:
    """`except aiohttp.ClientError` preceded `except TimeoutError`, and in
    aiohttp 3.13.5 **all three** timeout classes subclass both, so the 504 branch
    was unreachable outright — every timed-out upstream was reported as a 502."""

    @pytest.mark.parametrize(
        "cls_name",
        ["ServerTimeoutError", "SocketTimeoutError", "ConnectionTimeoutError"],
    )
    def test_timeout_classes_subclass_both(self, cls_name):
        cls = getattr(aiohttp, cls_name, None)
        if cls is None:
            pytest.skip(f"{cls_name} absent in aiohttp {aiohttp.__version__}")
        assert issubclass(cls, aiohttp.ClientError)
        assert issubclass(cls, TimeoutError), (
            "precondition for this finding no longer holds — recheck the "
            "except ordering in http_client.session()"
        )

    def test_except_timeout_is_ordered_before_client_error(self):
        """Asserted on the source because reaching the handler needs a live
        session; the ordering *is* the contract."""
        import inspect

        from src._core.infrastructure.http import http_client

        src = inspect.getsource(http_client.HttpClient.session)
        assert src.index("except TimeoutError") < src.index(
            "except aiohttp.ClientError"
        ), (
            "aiohttp timeout classes subclass ClientError too, so ClientError "
            "first makes ExternalServiceTimeoutException unreachable"
        )


class TestProviderMessageStaysOutOfStructlogKwargs:
    """`security-checklist.md:194` — "structlog kwargs / bind do not carry
    sensitive fields".

    A cross-review of the first version of this change proposed suppressing the
    provider text from logs entirely, via `from None`. That conflicts with the
    other half of #323: `custom_exception_handler` now logs a 5xx with
    `exc_info`, and the whole point is that the wrapped cause has nowhere else to
    live. So the split is deliberate — the **kwargs** stay clean, and the
    exception chain keeps the text for the traceback.

    These tests assert exactly that, and no more. An absolute "the ARN is not in
    the log output" assertion would be false, because the chained
    `__cause__` renders it.
    """

    def _kwargs_only(self, logs: list[dict]) -> str:
        """Rendered structured fields, excluding the exception chain."""
        return repr(
            [
                {k: v for k, v in rec.items() if k not in {"exc_info", "exception"}}
                for rec in logs
            ]
        )

    async def test_storage_failure_kwargs_carry_no_arn_key_or_account(self):
        from structlog.testing import capture_logs

        from src._core.infrastructure.storage.object_storage import ObjectStorage

        class _FailingClient:
            def client(self):
                raise _access_denied()

        storage = ObjectStorage(storage_client=_FailingClient(), bucket_name=BUCKET)
        with capture_logs() as logs:
            with pytest.raises(BaseCustomException):
                await storage.upload_file(b"x", KEY, "text/plain")

        rendered = self._kwargs_only(logs)
        assert logs, "the storage failure produced no log record at all"
        for secret, label in (
            (ARN, "IAM ARN"),
            (ACCOUNT, "account id"),
            (KEY, "object key"),
        ):
            assert secret not in rendered, (
                f"the {label} is a structlog kwarg: {rendered}"
            )
        assert "AccessDenied" in rendered, "the error code must still be logged"
        assert "ClientError" in rendered, (
            "the provider exception type must still be logged"
        )

    def test_the_exception_chain_still_carries_the_cause(self):
        """The other half of the contract — deliberately asserting the text IS
        reachable, so a future change cannot quietly drop the cause that F1
        exists to surface."""
        from src._core.infrastructure.storage.object_storage import _storage_failure

        original = _access_denied()
        try:
            raise _storage_failure("upload", original) from original
        except BaseCustomException as exc:
            assert exc.__cause__ is original
            assert ARN in str(exc.__cause__)
