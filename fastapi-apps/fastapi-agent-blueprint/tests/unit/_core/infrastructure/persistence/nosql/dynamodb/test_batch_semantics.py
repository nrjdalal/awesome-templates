"""Batch and bound semantics for `BaseDynamoRepository` (#329).

Three fail-open defects, all reachable by any adopter who subclasses the base —
which is the whole point of a base class shipped in a template.

**F6.** `batch_put_items` retried `UnprocessedItems` up to `max_retries` with no
backoff and no sleep, then fell through and built a success DTO for *every* item
in the chunk, including ones DynamoDB explicitly refused. No exception, no log.
Measured before the fix: 30 entities submitted, 30 DTOs returned, 6
`batch_write_item` calls, zero backoff, nothing raised. DynamoDB returns
`UnprocessedItems` precisely under throughput throttling — the case where three
immediate un-backed-off retries are most likely to all fail. `batch_get_items`
dropped leftover `UnprocessedKeys`, so the caller got a short list
indistinguishable from "those keys do not exist".

**F11.** `if limit:` instead of `if limit is not None:` — `limit=0` was silently
discarded and the query returned a full page. Same failure shape as the vector
filters in #328: a caller-supplied bound dropped rather than honoured or rejected.

**Cursor.** `_decode_cursor` ran `json.loads(b64decode(...))` on a client-supplied
token with no guard, so a malformed cursor escaped as a raw `binascii.Error` /
`JSONDecodeError` — a 500 where a curated 400 belongs, and since #17 a 500 also
fires a webhook alert.

Decision recorded here because the issue left it open: both batch methods
**raise** on exhaustion, carrying the unprocessed count, rather than returning a
partial result. For writes that is the only safe answer. For reads it discards
successful work in the same call, which is acceptable because reads are
idempotent and cheap to redo, while a silently short list is not detectable at
all. The exception is a new `DynamoDBBatchIncompleteException` rather than the
existing `DynamoDBThrottlingException`: throttling is the usual cause but not the
only one, and the count is what a caller needs to act.
"""

# The client parameters below are annotated with their concrete wrapper classes
# on purpose: `ObjectStorage`, `BaseS3VectorStore` and the notification adapters
# reach through `client()` / `session` to a *typed* boto or aiohttp object, and
# that annotation is what type-checks the provider calls inside them (#386). A
# protocol loose enough to admit a double would give that up, so the doubles are
# accepted here instead, at the one line where the substitution happens.
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import ClassVar

import pytest
from pydantic import BaseModel

from src._core.domain.value_objects.dynamo_key import DynamoKey
from src._core.infrastructure.persistence.nosql.dynamodb.base_dynamo_repository import (
    BaseDynamoRepository,
)
from src._core.infrastructure.persistence.nosql.dynamodb.dynamodb_model import (
    DynamoModel,
    DynamoModelMeta,
)
from src._core.infrastructure.persistence.nosql.dynamodb.exceptions import (
    DynamoDBBatchIncompleteException,
    DynamoDBException,
    DynamoDBInvalidLimitException,
)


class _NoteDTO(BaseModel):
    user_id: str = ""
    note_id: str = ""
    title: str = ""
    content: str = ""


class _NoteModel(DynamoModel):
    __dynamo_meta__: ClassVar[DynamoModelMeta] = DynamoModelMeta(
        tablename="test_notes",
        partition_key_name="PK",
        sort_key_name="SK",
    )

    user_id: str
    note_id: str
    title: str = ""
    content: str = ""

    def get_partition_key(self) -> str:
        return "USER#" + self.user_id

    def get_sort_key(self) -> str:
        return "NOTE#" + self.note_id


class _RefusingClient:
    """Refuses everything, the way a throttled table does."""

    def __init__(self, *, refuse_writes: bool = False, refuse_reads: bool = False):
        self.refuse_writes = refuse_writes
        self.refuse_reads = refuse_reads
        self.write_calls = 0
        self.read_calls = 0
        self.query_params: dict | None = None

    async def batch_write_item(self, *, RequestItems: dict, **_kw) -> dict:  # noqa: N803
        self.write_calls += 1
        return {"UnprocessedItems": RequestItems if self.refuse_writes else {}}

    async def batch_get_item(self, *, RequestItems: dict, **_kw) -> dict:  # noqa: N803
        self.read_calls += 1
        return {
            "Responses": {},
            "UnprocessedKeys": RequestItems if self.refuse_reads else {},
        }

    async def query(self, **params) -> dict:
        self.query_params = params
        return {"Items": []}


class _PartialClient:
    """Refuses a shrinking slice, the way a recovering table does.

    `_RefusingClient` only models all-or-nothing. DynamoDB's actual response is
    partial: some items land, the rest come back as UnprocessedItems. That
    difference is where the accumulate-then-raise logic can go wrong, so it
    needs its own double.
    """

    def __init__(self, refuse_rounds: int) -> None:
        self.refuse_rounds = refuse_rounds
        self.write_calls = 0
        self.read_calls = 0
        self.sleeps: list[float] = []

    async def batch_write_item(self, *, RequestItems: dict, **_kw) -> dict:  # noqa: N803
        self.write_calls += 1
        if self.write_calls <= self.refuse_rounds:
            # Hold back the tail, accept the head.
            table, requests = next(iter(RequestItems.items()))
            return {"UnprocessedItems": {table: requests[len(requests) // 2 :]}}
        return {"UnprocessedItems": {}}

    async def batch_get_item(self, *, RequestItems: dict, **_kw) -> dict:  # noqa: N803
        self.read_calls += 1
        if self.read_calls <= self.refuse_rounds:
            table, spec = next(iter(RequestItems.items()))
            keys = spec["Keys"]
            return {
                "Responses": {},
                "UnprocessedKeys": {table: {"Keys": keys[len(keys) // 2 :]}},
            }
        return {"Responses": {}, "UnprocessedKeys": {}}

    async def query(self, **params) -> dict:  # pragma: no cover - unused
        return {"Items": []}


class _FakeDynamoDBClient:
    def __init__(self, inner: _RefusingClient) -> None:
        self._inner = inner

    @asynccontextmanager
    async def client(self):
        yield self._inner


class _NoteRepository(BaseDynamoRepository[_NoteDTO]):
    def __init__(self, dynamodb_client) -> None:
        super().__init__(
            dynamodb_client=dynamodb_client,
            model=_NoteModel,
            return_entity=_NoteDTO,
        )


def _repository(inner: _RefusingClient) -> _NoteRepository:
    return _NoteRepository(dynamodb_client=_FakeDynamoDBClient(inner))


def _entities(count: int) -> list[_NoteDTO]:
    return [_NoteDTO(user_id="u", note_id=str(i), title=f"t{i}") for i in range(count)]


class TestBatchPutRefusedWrites:
    @pytest.mark.asyncio
    async def test_raises_instead_of_reporting_success(self) -> None:
        # Previously: 30 entities in, 30 success DTOs out, nothing raised.
        client = _RefusingClient(refuse_writes=True)
        repository = _repository(client)

        with pytest.raises(DynamoDBBatchIncompleteException) as exc:
            await repository.batch_put_items(_entities(30), max_retries=2)

        assert exc.value.status_code == 503
        assert exc.value.error_code == "DYNAMODB_BATCH_INCOMPLETE"

    @pytest.mark.asyncio
    async def test_the_error_carries_the_unprocessed_count(self) -> None:
        client = _RefusingClient(refuse_writes=True)

        with pytest.raises(DynamoDBBatchIncompleteException) as exc:
            await _repository(client).batch_put_items(_entities(5), max_retries=2)

        # The count measures the failure; it does not identify the items.
        # Re-submitting means replaying the batch, not cherry-picking from a
        # list this exception does not carry.
        assert "5" in exc.value.message

    @pytest.mark.asyncio
    async def test_it_is_a_dynamodb_exception(self) -> None:
        # So existing `except DynamoDBException` handlers keep working.
        assert issubclass(DynamoDBBatchIncompleteException, DynamoDBException)

    @pytest.mark.asyncio
    async def test_a_clean_write_still_returns_dtos(self) -> None:
        client = _RefusingClient(refuse_writes=False)

        results = await _repository(client).batch_put_items(_entities(30))

        assert len(results) == 30
        assert client.write_calls == 2  # 25 + 5, one call each, no retries

    @pytest.mark.asyncio
    async def test_retries_are_bounded_by_max_retries(self) -> None:
        client = _RefusingClient(refuse_writes=True)

        with pytest.raises(DynamoDBBatchIncompleteException):
            await _repository(client).batch_put_items(_entities(1), max_retries=3)

        assert client.write_calls == 3


class TestBatchGetRefusedKeys:
    @pytest.mark.asyncio
    async def test_raises_instead_of_returning_a_short_list(self) -> None:
        # Previously: 0 items for 1 key, no error — indistinguishable from
        # "that key does not exist".
        client = _RefusingClient(refuse_reads=True)

        with pytest.raises(DynamoDBBatchIncompleteException):
            await _repository(client).batch_get_items(
                [DynamoKey(partition_key="a")], max_retries=2
            )

    @pytest.mark.asyncio
    async def test_a_clean_read_does_not_raise(self) -> None:
        client = _RefusingClient(refuse_reads=False)

        results = await _repository(client).batch_get_items(
            [DynamoKey(partition_key="a")]
        )

        assert results == []
        assert client.read_calls == 1


class TestQueryLimitBound:
    @pytest.mark.parametrize("limit", [0, -1])
    @pytest.mark.asyncio
    async def test_a_sub_one_limit_is_a_client_error_not_a_500(
        self, limit: int
    ) -> None:
        """DynamoDB requires Limit >= 1, so forwarding it is not an option.

        The status matters as much as the rejection. The first fix raised a bare
        ``ValueError``, which the generic handler turns into
        ``INTERNAL_SERVER_ERROR`` — trading a silently dropped bound for a 500
        and an operator page on a malformed request. `query_items` is reachable
        from adopter request paths, so it has to be a 4xx.
        """
        with pytest.raises(DynamoDBInvalidLimitException) as exc:
            await _repository(_RefusingClient()).query_items(
                partition_key_value="a", limit=limit
            )

        assert exc.value.status_code == 400
        assert exc.value.error_code == "DYNAMODB_INVALID_LIMIT"
        assert isinstance(exc.value, DynamoDBException)

    @pytest.mark.asyncio
    async def test_a_positive_limit_is_forwarded(self) -> None:
        client = _RefusingClient()

        await _repository(client).query_items(partition_key_value="a", limit=7)

        assert client.query_params is not None
        assert client.query_params["Limit"] == 7

    @pytest.mark.asyncio
    async def test_none_means_unbounded(self) -> None:
        client = _RefusingClient()

        await _repository(client).query_items(partition_key_value="a", limit=None)

        assert client.query_params is not None
        assert "Limit" not in client.query_params


class TestCursorGuard:
    @pytest.mark.parametrize("cursor", ["not-base64!!", "YWJj", "", "eyJhIjog"])
    def test_a_malformed_cursor_is_a_curated_error(self, cursor: str) -> None:
        # Raw binascii.Error / JSONDecodeError would surface as a 500 — and
        # since #17 a 500 also fires a webhook alert.
        with pytest.raises(DynamoDBException) as exc:
            BaseDynamoRepository._decode_cursor(cursor)

        assert exc.value.status_code == 400

    def test_a_round_tripped_cursor_still_decodes(self) -> None:
        key = {"note_id": {"S": "42"}}

        encoded = BaseDynamoRepository._encode_cursor(key)

        assert BaseDynamoRepository._decode_cursor(encoded) == key

    def test_a_json_scalar_is_rejected(self) -> None:
        # Valid base64 and valid JSON, but not a key mapping — forwarding it as
        # ExclusiveStartKey would fail inside the AWS call instead.
        import base64

        encoded = base64.urlsafe_b64encode(b"42").decode()

        with pytest.raises(DynamoDBException):
            BaseDynamoRepository._decode_cursor(encoded)


class TestRetryBehaviour:
    """Shapes the first round of tests missed, per cross-review."""

    @pytest.mark.asyncio
    async def test_a_later_retry_succeeding_does_not_raise(self) -> None:
        client = _PartialClient(refuse_rounds=1)

        results = await _repository(client).batch_put_items(_entities(4), max_retries=3)  # pyright: ignore[reportArgumentType]

        assert len(results) == 4
        assert client.write_calls == 2  # refused once, then accepted

    @pytest.mark.asyncio
    async def test_no_sleep_after_the_final_attempt(self, monkeypatch) -> None:
        # A wait after the last try is pure added latency before an exception.
        slept: list[float] = []

        async def _record(delay: float) -> None:
            slept.append(delay)

        monkeypatch.setattr(
            "src._core.infrastructure.persistence.nosql.dynamodb"
            ".base_dynamo_repository.asyncio.sleep",
            _record,
        )
        client = _RefusingClient(refuse_writes=True)

        with pytest.raises(DynamoDBBatchIncompleteException):
            await _repository(client).batch_put_items(_entities(1), max_retries=3)

        assert client.write_calls == 3
        assert len(slept) == 2  # between attempts only

    @pytest.mark.asyncio
    async def test_backoff_grows_and_is_jittered(self, monkeypatch) -> None:
        slept: list[float] = []

        async def _record(delay: float) -> None:
            slept.append(delay)

        monkeypatch.setattr(
            "src._core.infrastructure.persistence.nosql.dynamodb"
            ".base_dynamo_repository.asyncio.sleep",
            _record,
        )

        with pytest.raises(DynamoDBBatchIncompleteException):
            await _repository(_RefusingClient(refuse_writes=True)).batch_put_items(
                _entities(1), max_retries=3
            )

        # Jitter is half-to-full of an exponential ceiling, so the second wait
        # can never be below the first's floor.
        assert slept[1] > slept[0] / 2

    @pytest.mark.asyncio
    async def test_empty_input_calls_nothing(self) -> None:
        client = _RefusingClient(refuse_writes=True)

        assert await _repository(client).batch_put_items([]) == []
        assert client.write_calls == 0

    @pytest.mark.asyncio
    async def test_exactly_one_chunk_at_the_write_boundary(self) -> None:
        client = _RefusingClient()

        await _repository(client).batch_put_items(_entities(25))

        assert client.write_calls == 1

    @pytest.mark.asyncio
    async def test_one_over_the_write_boundary_is_two_chunks(self) -> None:
        client = _RefusingClient()

        await _repository(client).batch_put_items(_entities(26))

        assert client.write_calls == 2

    @pytest.mark.asyncio
    async def test_exactly_one_chunk_at_the_read_boundary(self) -> None:
        client = _RefusingClient()

        await _repository(client).batch_get_items(
            [DynamoKey(partition_key=str(i)) for i in range(100)]
        )

        assert client.read_calls == 1
