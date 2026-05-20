"""Integration tests for BaseDynamoRepository against DynamoDB Local.

Requires: docker-compose up dynamodb-local
"""

import contextlib
from typing import ClassVar

import pytest
import pytest_asyncio
from pydantic import BaseModel

from src._core.domain.value_objects.cursor_page import CursorPage
from src._core.domain.value_objects.dynamo_key import DynamoKey, SortKeyCondition
from src._core.infrastructure.persistence.nosql.dynamodb.base_dynamo_repository import (
    BaseDynamoRepository,
)
from src._core.infrastructure.persistence.nosql.dynamodb.dynamodb_client import (
    DynamoDBClient,
)
from src._core.infrastructure.persistence.nosql.dynamodb.dynamodb_model import (
    DynamoModel,
    DynamoModelMeta,
    GSIDefinition,
)
from src._core.infrastructure.persistence.nosql.dynamodb.exceptions import (
    DynamoDBNotFoundException,
)

DYNAMODB_ENDPOINT = "http://localhost:8000"
TABLE_NAME = "test_integration_notes"


# ── Model / DTO / Repository ──────────────────────────────────


class NoteModel(DynamoModel):
    __dynamo_meta__: ClassVar[DynamoModelMeta] = DynamoModelMeta(
        tablename=TABLE_NAME,
        partition_key_name="PK",
        sort_key_name="SK",
        gsi=[
            GSIDefinition(
                index_name="GSI1",
                partition_key_name="GSI1PK",
                sort_key_name="GSI1SK",
            )
        ],
    )

    user_id: str
    note_id: str
    title: str
    content: str = ""

    def get_partition_key(self) -> str:
        return "USER#" + self.user_id

    def get_sort_key(self) -> str:
        return "NOTE#" + self.note_id

    def get_gsi_GSI1_pk(self) -> str:
        return "USER#" + self.user_id

    def get_gsi_GSI1_sk(self) -> str:
        return "TITLE#" + self.title


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


class UpdateNoteRequest(BaseModel):
    title: str | None = None
    content: str | None = None


class NoteRepository(BaseDynamoRepository[NoteDTO]):
    def __init__(self, dynamodb_client: DynamoDBClient) -> None:
        super().__init__(
            dynamodb_client=dynamodb_client,
            model=NoteModel,
            return_entity=NoteDTO,
        )


# ── Fixtures ──────────────────────────────────────────────────


@pytest_asyncio.fixture(scope="module")
async def dynamodb_client():
    client = DynamoDBClient(
        access_key="testing",
        secret_access_key="testing",
        region_name="us-east-1",
        endpoint_url=DYNAMODB_ENDPOINT,
    )

    # Create table
    async with client.client() as c:
        try:
            await c.describe_table(TableName=TABLE_NAME)
        except Exception:
            await c.create_table(
                TableName=TABLE_NAME,
                KeySchema=[
                    {"AttributeName": "PK", "KeyType": "HASH"},
                    {"AttributeName": "SK", "KeyType": "RANGE"},
                ],
                AttributeDefinitions=[
                    {"AttributeName": "PK", "AttributeType": "S"},
                    {"AttributeName": "SK", "AttributeType": "S"},
                    {"AttributeName": "GSI1PK", "AttributeType": "S"},
                    {"AttributeName": "GSI1SK", "AttributeType": "S"},
                ],
                GlobalSecondaryIndexes=[
                    {
                        "IndexName": "GSI1",
                        "KeySchema": [
                            {"AttributeName": "GSI1PK", "KeyType": "HASH"},
                            {"AttributeName": "GSI1SK", "KeyType": "RANGE"},
                        ],
                        "Projection": {"ProjectionType": "ALL"},
                    }
                ],
                BillingMode="PAY_PER_REQUEST",
            )

    yield client

    # Cleanup table
    async with client.client() as c:
        with contextlib.suppress(Exception):
            await c.delete_table(TableName=TABLE_NAME)


@pytest.fixture
def repo(dynamodb_client):
    return NoteRepository(dynamodb_client=dynamodb_client)


# ── Tests ──────────────────────────────────────────────────────


class TestCRUD:
    @pytest.mark.asyncio
    async def test_put_and_get(self, repo):
        request = CreateNoteRequest(
            user_id="u1", note_id="n1", title="Hello", content="World"
        )
        created = await repo.put_item(entity=request)
        assert created.user_id == "u1"
        assert created.title == "Hello"

        fetched = await repo.get_item(
            key=DynamoKey(partition_key="USER#u1", sort_key="NOTE#n1")
        )
        assert fetched.title == "Hello"
        assert fetched.content == "World"

    @pytest.mark.asyncio
    async def test_get_nonexistent_raises_404(self, repo):
        with pytest.raises(DynamoDBNotFoundException):
            await repo.get_item(
                key=DynamoKey(partition_key="USER#none", sort_key="NOTE#none")
            )

    @pytest.mark.asyncio
    async def test_update(self, repo):
        await repo.put_item(
            entity=CreateNoteRequest(user_id="u2", note_id="n1", title="Old")
        )
        updated = await repo.update_item(
            key=DynamoKey(partition_key="USER#u2", sort_key="NOTE#n1"),
            entity=UpdateNoteRequest(title="New"),
        )
        assert updated.title == "New"

    @pytest.mark.asyncio
    async def test_delete(self, repo):
        await repo.put_item(
            entity=CreateNoteRequest(user_id="u3", note_id="n1", title="ToDelete")
        )
        result = await repo.delete_item(
            key=DynamoKey(partition_key="USER#u3", sort_key="NOTE#n1")
        )
        assert result is True

        with pytest.raises(DynamoDBNotFoundException):
            await repo.get_item(
                key=DynamoKey(partition_key="USER#u3", sort_key="NOTE#n1")
            )


class TestQuery:
    @pytest.mark.asyncio
    async def test_query_by_partition_key(self, repo):
        for i in range(3):
            await repo.put_item(
                entity=CreateNoteRequest(
                    user_id="q1",
                    note_id="n" + str(i),
                    title="Note " + str(i),
                )
            )

        result = await repo.query_items(partition_key_value="USER#q1")
        assert isinstance(result, CursorPage)
        assert result.count == 3

    @pytest.mark.asyncio
    async def test_query_with_sort_key_condition(self, repo):
        for i in range(3):
            await repo.put_item(
                entity=CreateNoteRequest(
                    user_id="q2",
                    note_id="n" + str(i),
                    title="Note " + str(i),
                )
            )

        result = await repo.query_items(
            partition_key_value="USER#q2",
            sort_key_condition=SortKeyCondition(
                operator="begins_with", value="NOTE#n1"
            ),
        )
        assert result.count == 1
        assert result.items[0].note_id == "n1"

    @pytest.mark.asyncio
    async def test_query_with_limit_and_cursor(self, repo):
        for i in range(5):
            await repo.put_item(
                entity=CreateNoteRequest(
                    user_id="q3",
                    note_id="n" + str(i),
                    title="Note " + str(i),
                )
            )

        page1 = await repo.query_items(partition_key_value="USER#q3", limit=2)
        assert page1.count == 2
        assert page1.next_cursor is not None

        page2 = await repo.query_items(
            partition_key_value="USER#q3",
            limit=2,
            cursor=page1.next_cursor,
        )
        assert page2.count == 2

    @pytest.mark.asyncio
    async def test_query_with_filter_expression(self, repo):
        await repo.put_item(
            entity=CreateNoteRequest(
                user_id="q4", note_id="n1", title="Active", content="yes"
            )
        )
        await repo.put_item(
            entity=CreateNoteRequest(
                user_id="q4", note_id="n2", title="Inactive", content="no"
            )
        )

        result = await repo.query_items(
            partition_key_value="USER#q4",
            filter_expression="#content = :content",
            expression_attribute_names={"#content": "content"},
            expression_attribute_values={":content": "yes"},
        )
        assert result.count == 1
        assert result.items[0].title == "Active"

    @pytest.mark.asyncio
    async def test_query_gsi(self, repo):
        await repo.put_item(
            entity=CreateNoteRequest(user_id="q5", note_id="n1", title="Alpha")
        )
        await repo.put_item(
            entity=CreateNoteRequest(user_id="q5", note_id="n2", title="Beta")
        )

        result = await repo.query_items(
            partition_key_value="USER#q5",
            index_name="GSI1",
            sort_key_condition=SortKeyCondition(
                operator="begins_with", value="TITLE#A"
            ),
        )
        assert result.count == 1
        assert result.items[0].title == "Alpha"


class TestBatch:
    @pytest.mark.asyncio
    async def test_batch_put_and_get(self, repo):
        entities = [
            CreateNoteRequest(
                user_id="b1",
                note_id="n" + str(i),
                title="Batch " + str(i),
            )
            for i in range(5)
        ]
        results = await repo.batch_put_items(entities=entities)
        assert len(results) == 5

        keys = [
            DynamoKey(partition_key="USER#b1", sort_key="NOTE#n" + str(i))
            for i in range(5)
        ]
        fetched = await repo.batch_get_items(keys=keys)
        assert len(fetched) == 5
