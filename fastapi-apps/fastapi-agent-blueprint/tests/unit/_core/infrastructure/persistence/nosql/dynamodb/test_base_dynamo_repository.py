"""Unit tests for BaseDynamoRepository using a mock DynamoDB client."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, ClassVar

import pytest
from boto3.dynamodb.types import TypeDeserializer, TypeSerializer
from pydantic import BaseModel

from src._core.domain.value_objects.cursor_page import CursorPage
from src._core.domain.value_objects.dynamo_key import DynamoKey, SortKeyCondition
from src._core.infrastructure.persistence.nosql.dynamodb.base_dynamo_repository import (
    BaseDynamoRepository,
)
from src._core.infrastructure.persistence.nosql.dynamodb.dynamodb_model import (
    DynamoModel,
    DynamoModelMeta,
)
from src._core.infrastructure.persistence.nosql.dynamodb.exceptions import (
    DynamoDBNotFoundException,
)

# ── Test fixtures ──────────────────────────────────────────────


class NoteModel(DynamoModel):
    __dynamo_meta__: ClassVar[DynamoModelMeta] = DynamoModelMeta(
        tablename="test_notes",
        partition_key_name="PK",
        sort_key_name="SK",
    )

    user_id: str
    note_id: str
    title: str
    content: str = ""

    def get_partition_key(self) -> str:
        return "USER#" + self.user_id

    def get_sort_key(self) -> str:
        return "NOTE#" + self.note_id


class NoteDTO(BaseModel):
    user_id: str
    note_id: str
    title: str
    content: str = ""


class CreateNoteRequest(BaseModel):
    user_id: str
    note_id: str
    title: str
    content: str = ""


class FakeClient:
    """In-memory DynamoDB client mock that stores raw DynamoDB-typed items."""

    def __init__(self):
        self._tables: dict[str, list[dict[str, Any]]] = {}
        self._serializer = TypeSerializer()
        self._deserializer = TypeDeserializer()

    async def put_item(self, *, TableName: str, Item: dict, **kwargs):
        self._tables.setdefault(TableName, [])
        # Overwrite existing item with same key
        pk_val = Item.get("PK")
        sk_val = Item.get("SK")
        self._tables[TableName] = [
            i
            for i in self._tables[TableName]
            if not (i.get("PK") == pk_val and i.get("SK") == sk_val)
        ]
        self._tables[TableName].append(Item)

    async def get_item(self, *, TableName: str, Key: dict, **kwargs):
        items = self._tables.get(TableName, [])
        for item in items:
            if all(item.get(k) == v for k, v in Key.items()):
                return {"Item": item}
        return {}

    async def query(self, *, TableName: str, **kwargs):
        # Return all items for simplicity
        items = self._tables.get(TableName, [])
        limit = kwargs.get("Limit")
        if limit:
            return {"Items": items[:limit], "Count": min(limit, len(items))}
        return {"Items": items, "Count": len(items)}

    async def update_item(
        self, *, TableName: str, Key: dict, ReturnValues: str = "ALL_NEW", **kwargs
    ):
        items = self._tables.get(TableName, [])
        for item in items:
            if all(item.get(k) == v for k, v in Key.items()):
                # Parse simple SET expressions
                expr_names = kwargs.get("ExpressionAttributeNames", {})
                expr_values = kwargs.get("ExpressionAttributeValues", {})
                for name_key, val_key in zip(
                    sorted(expr_names.keys()),
                    sorted(expr_values.keys()),
                    strict=False,
                ):
                    field_name = expr_names[name_key]
                    item[field_name] = expr_values[val_key]
                return {"Attributes": item}
        return {"Attributes": {}}

    async def delete_item(self, *, TableName: str, Key: dict, **kwargs):
        items = self._tables.get(TableName, [])
        self._tables[TableName] = [
            i for i in items if not all(i.get(k) == v for k, v in Key.items())
        ]

    async def batch_write_item(self, *, RequestItems: dict, **kwargs):
        for table_name, requests in RequestItems.items():
            for req in requests:
                if "PutRequest" in req:
                    await self.put_item(
                        TableName=table_name, Item=req["PutRequest"]["Item"]
                    )
        return {}

    async def batch_get_item(self, *, RequestItems: dict, **kwargs):
        responses = {}
        for table_name, spec in RequestItems.items():
            items = []
            for key in spec["Keys"]:
                result = await self.get_item(TableName=table_name, Key=key)
                if "Item" in result:
                    items.append(result["Item"])
            responses[table_name] = items
        return {"Responses": responses}


class FakeDynamoDBClient:
    def __init__(self):
        self._client = FakeClient()

    @asynccontextmanager
    async def client(self):
        yield self._client


class NoteRepository(BaseDynamoRepository[NoteDTO]):
    def __init__(self, dynamodb_client):
        super().__init__(
            dynamodb_client=dynamodb_client,
            model=NoteModel,
            return_entity=NoteDTO,
        )


@pytest.fixture
def repo():
    return NoteRepository(dynamodb_client=FakeDynamoDBClient())


# ── Tests ──────────────────────────────────────────────────────


class TestPutAndGet:
    @pytest.mark.asyncio
    async def test_put_and_get_item(self, repo):
        request = CreateNoteRequest(user_id="u1", note_id="n1", title="Hello")
        created = await repo.put_item(entity=request)

        assert created.user_id == "u1"
        assert created.note_id == "n1"
        assert created.title == "Hello"

        fetched = await repo.get_item(
            key=DynamoKey(partition_key="USER#u1", sort_key="NOTE#n1")
        )
        assert fetched.title == "Hello"

    @pytest.mark.asyncio
    async def test_get_nonexistent_raises_404(self, repo):
        with pytest.raises(DynamoDBNotFoundException):
            await repo.get_item(
                key=DynamoKey(partition_key="USER#x", sort_key="NOTE#x")
            )


class TestQuery:
    @pytest.mark.asyncio
    async def test_query_returns_cursor_page(self, repo):
        for i in range(3):
            await repo.put_item(
                entity=CreateNoteRequest(
                    user_id="u1",
                    note_id="n" + str(i),
                    title="Note " + str(i),
                )
            )

        result = await repo.query_items(partition_key_value="USER#u1")

        assert isinstance(result, CursorPage)
        assert result.count == 3
        assert len(result.items) == 3

    @pytest.mark.asyncio
    async def test_query_with_limit(self, repo):
        for i in range(5):
            await repo.put_item(
                entity=CreateNoteRequest(
                    user_id="u1",
                    note_id="n" + str(i),
                    title="Note " + str(i),
                )
            )

        result = await repo.query_items(partition_key_value="USER#u1", limit=2)
        assert result.count == 2


class TestUpdate:
    @pytest.mark.asyncio
    async def test_update_item(self, repo):
        await repo.put_item(
            entity=CreateNoteRequest(user_id="u1", note_id="n1", title="Old")
        )

        class UpdateRequest(BaseModel):
            title: str

        updated = await repo.update_item(
            key=DynamoKey(partition_key="USER#u1", sort_key="NOTE#n1"),
            entity=UpdateRequest(title="New"),
        )
        assert updated.title == "New"


class TestDelete:
    @pytest.mark.asyncio
    async def test_delete_item(self, repo):
        await repo.put_item(
            entity=CreateNoteRequest(user_id="u1", note_id="n1", title="ToDelete")
        )

        result = await repo.delete_item(
            key=DynamoKey(partition_key="USER#u1", sort_key="NOTE#n1")
        )
        assert result is True

        with pytest.raises(DynamoDBNotFoundException):
            await repo.get_item(
                key=DynamoKey(partition_key="USER#u1", sort_key="NOTE#n1")
            )


class TestBatch:
    @pytest.mark.asyncio
    async def test_batch_put_items(self, repo):
        entities = [
            CreateNoteRequest(
                user_id="u1", note_id="n" + str(i), title="Batch " + str(i)
            )
            for i in range(3)
        ]
        results = await repo.batch_put_items(entities=entities)
        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_batch_get_items(self, repo):
        for i in range(3):
            await repo.put_item(
                entity=CreateNoteRequest(
                    user_id="u1",
                    note_id="n" + str(i),
                    title="Note " + str(i),
                )
            )

        keys = [
            DynamoKey(partition_key="USER#u1", sort_key="NOTE#n" + str(i))
            for i in range(3)
        ]
        results = await repo.batch_get_items(keys=keys)
        assert len(results) == 3
