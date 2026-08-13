"""`list_files` must return only keys a caller can actually address (#381).

`Key` is optional in the `list_objects_v2` response model, so `obj["Key"]` was an
unguarded `KeyError` — found by widening pyright over
`_core/infrastructure/storage`, and reachable only through a response real S3
does not send. It stayed invisible because the sole existing test for this method
covers the `ClientError` path, not the happy one.

The chosen behaviour is to skip such an entry rather than surface `""`: this
method's contract is "keys you can address", and an empty key handed to
`download_file` or `delete_file` is worse than a shorter list.
"""

# The client parameters below are annotated with their concrete wrapper classes
# on purpose: `ObjectStorage`, `BaseS3VectorStore` and the notification adapters
# reach through `client()` / `session` to a *typed* boto or aiohttp object, and
# that annotation is what type-checks the provider calls inside them (#386). A
# protocol loose enough to admit a double would give that up, so the doubles are
# accepted here instead, at the one line where the substitution happens.
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

import pytest

from src._core.infrastructure.storage.object_storage import ObjectStorage

BUCKET = "test-bucket"


def _storage(response: dict[str, Any]) -> ObjectStorage:
    class _Client:
        async def list_objects_v2(self, **_: Any) -> dict[str, Any]:
            return response

    class _StorageClient:
        @asynccontextmanager
        async def client(self):
            yield _Client()

    return ObjectStorage(storage_client=_StorageClient(), bucket_name=BUCKET)  # pyright: ignore[reportArgumentType]


@pytest.mark.asyncio
async def test_returns_every_key_in_response_order() -> None:
    storage = _storage({"Contents": [{"Key": "a.txt"}, {"Key": "b/c.txt"}]})
    assert await storage.list_files() == ["a.txt", "b/c.txt"]


@pytest.mark.asyncio
async def test_missing_contents_is_an_empty_list_not_an_error() -> None:
    """An empty bucket or a prefix that matches nothing omits `Contents`."""
    assert await _storage({}).list_files() == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "unusable",
    [{}, {"Key": ""}, {"Size": 12}],
    ids=["no-key", "empty-key", "other-fields-only"],
)
async def test_an_entry_without_a_usable_key_is_skipped(
    unusable: dict[str, Any],
) -> None:
    storage = _storage({"Contents": [{"Key": "a.txt"}, unusable, {"Key": "b.txt"}]})

    # The keyless entry is dropped, and — the part that used to raise — the
    # entries after it are still returned.
    assert await storage.list_files() == ["a.txt", "b.txt"]
