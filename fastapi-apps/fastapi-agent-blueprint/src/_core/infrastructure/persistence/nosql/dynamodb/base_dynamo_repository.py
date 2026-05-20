from __future__ import annotations

import base64
import json
from abc import ABC
from typing import Any, Generic, TypeVar

from pydantic import BaseModel

from src._core.domain.value_objects.cursor_page import CursorPage
from src._core.domain.value_objects.dynamo_key import DynamoKey, SortKeyCondition
from src._core.infrastructure.persistence.nosql.dynamodb.dynamodb_client import (
    DynamoDBClient,
)
from src._core.infrastructure.persistence.nosql.dynamodb.dynamodb_model import (
    DynamoModel,
    _get_deserializer,
    _get_serializer,
)
from src._core.infrastructure.persistence.nosql.dynamodb.exceptions import (
    DynamoDBNotFoundException,
)

ReturnDTO = TypeVar("ReturnDTO", bound=BaseModel)

_SORT_KEY_OPS = {
    "eq": "{name} = {val}",
    "begins_with": "begins_with({name}, {val})",
    "lt": "{name} < {val}",
    "lte": "{name} <= {val}",
    "gt": "{name} > {val}",
    "gte": "{name} >= {val}",
    "between": "{name} BETWEEN {val} AND {val2}",
}


class BaseDynamoRepository(Generic[ReturnDTO], ABC):
    """Base repository for DynamoDB operations.

    Parallels ``BaseRepository[ReturnDTO]`` for RDB.
    Constructor takes ``DynamoDBClient``, ``DynamoModel`` class, and
    the return DTO class — same shape as the RDB base.
    """

    def __init__(
        self,
        dynamodb_client: DynamoDBClient,
        *,
        model: type[DynamoModel],
        return_entity: type[ReturnDTO],
    ) -> None:
        self.dynamodb_client = dynamodb_client
        self.model = model
        self.return_entity = return_entity
        self._serializer = _get_serializer()
        self._deserializer = _get_deserializer()

    @property
    def table_name(self) -> str:
        return self.model.__dynamo_meta__.tablename

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    async def put_item(self, entity: BaseModel) -> ReturnDTO:
        """Create or overwrite an item."""
        item = self.model(**entity.model_dump(exclude_none=True))
        async with self.dynamodb_client.client() as client:
            await client.put_item(
                TableName=self.table_name,
                Item=item.to_dynamodb(),
            )
        return self.return_entity.model_validate(
            item.model_dump(), from_attributes=True
        )

    async def get_item(self, key: DynamoKey) -> ReturnDTO:
        """Get a single item by primary key."""
        async with self.dynamodb_client.client() as client:
            response = await client.get_item(
                TableName=self.table_name,
                Key=self._serialize_key(key),
            )
        raw = response.get("Item")
        if not raw:
            raise DynamoDBNotFoundException()
        return self._deserialize_item(raw)

    async def query_items(
        self,
        partition_key_value: str,
        sort_key_condition: SortKeyCondition | None = None,
        index_name: str | None = None,
        filter_expression: str | None = None,
        expression_attribute_names: dict[str, str] | None = None,
        expression_attribute_values: dict[str, Any] | None = None,
        limit: int | None = None,
        cursor: str | None = None,
        scan_forward: bool = True,
    ) -> CursorPage[ReturnDTO]:
        """Query items by partition key with optional sort key and filter.

        ``filter_expression`` is applied after query (post-filter).
        Use ``expression_attribute_names`` / ``expression_attribute_values``
        to pass filter parameters safely (avoid raw value injection).

        Example::

            await repo.query_items(
                partition_key_value="ORG#123",
                filter_expression="#status = :status",
                expression_attribute_names={"#status": "status"},
                expression_attribute_values={":status": "active"},
            )
        """
        meta = self.model.__dynamo_meta__

        # Determine key names based on index or table
        if index_name:
            gsi = next((g for g in meta.gsi if g.index_name == index_name), None)
            if not gsi:
                raise ValueError(
                    "GSI '" + index_name + "' not defined on " + self.model.__name__
                )
            pk_name = gsi.partition_key_name
            sk_name = gsi.sort_key_name
        else:
            pk_name = meta.partition_key_name
            sk_name = meta.sort_key_name

        # Build KeyConditionExpression
        expr_names: dict[str, str] = {"#pk": pk_name}
        expr_values: dict[str, Any] = {
            ":pk": self._serializer.serialize(partition_key_value)
        }
        key_condition = "#pk = :pk"

        if sort_key_condition and sk_name:
            expr_names["#sk"] = sk_name
            expr_values[":skval"] = self._serializer.serialize(sort_key_condition.value)
            if sort_key_condition.operator == "between":
                expr_values[":skval2"] = self._serializer.serialize(
                    sort_key_condition.value2
                )

            template = _SORT_KEY_OPS[sort_key_condition.operator]
            sk_expr = template.format(name="#sk", val=":skval", val2=":skval2")
            key_condition += " AND " + sk_expr

        # Merge caller-provided expression attributes
        if expression_attribute_names:
            expr_names.update(expression_attribute_names)
        if expression_attribute_values:
            for k, v in expression_attribute_values.items():
                expr_values[k] = self._serializer.serialize(v)

        # Build query params
        params: dict[str, Any] = {
            "TableName": self.table_name,
            "KeyConditionExpression": key_condition,
            "ExpressionAttributeNames": expr_names,
            "ExpressionAttributeValues": expr_values,
            "ScanIndexForward": scan_forward,
        }
        if index_name:
            params["IndexName"] = index_name
        if filter_expression:
            params["FilterExpression"] = filter_expression
        if limit:
            params["Limit"] = limit
        if cursor:
            params["ExclusiveStartKey"] = self._decode_cursor(cursor)

        async with self.dynamodb_client.client() as client:
            response = await client.query(**params)

        items = [self._deserialize_item(raw) for raw in response.get("Items", [])]
        last_key = response.get("LastEvaluatedKey")

        return CursorPage(
            items=items,
            next_cursor=self._encode_cursor(last_key) if last_key else None,
            count=len(items),
        )

    async def update_item(self, key: DynamoKey, entity: BaseModel) -> ReturnDTO:
        """Update specific attributes of an item."""
        data = entity.model_dump(exclude_none=True)
        if not data:
            return await self.get_item(key)

        update_expr, expr_names, expr_values = self._build_update_expression(data)

        async with self.dynamodb_client.client() as client:
            response = await client.update_item(
                TableName=self.table_name,
                Key=self._serialize_key(key),
                UpdateExpression=update_expr,
                ExpressionAttributeNames=expr_names,
                ExpressionAttributeValues=expr_values,
                ReturnValues="ALL_NEW",
            )

        return self._deserialize_item(response["Attributes"])

    async def delete_item(self, key: DynamoKey) -> bool:
        """Delete an item by primary key."""
        async with self.dynamodb_client.client() as client:
            await client.delete_item(
                TableName=self.table_name,
                Key=self._serialize_key(key),
            )
        return True

    # ------------------------------------------------------------------
    # Batch operations
    # ------------------------------------------------------------------

    async def batch_put_items(
        self, entities: list[BaseModel], *, max_retries: int = 3
    ) -> list[ReturnDTO]:
        """Batch write items (auto-chunks to 25, retries UnprocessedItems)."""
        results: list[ReturnDTO] = []
        items = [self.model(**e.model_dump(exclude_none=True)) for e in entities]

        for i in range(0, len(items), 25):
            chunk = items[i : i + 25]
            requests = [{"PutRequest": {"Item": item.to_dynamodb()}} for item in chunk]

            pending: dict[str, list] = {self.table_name: requests}
            for _ in range(max_retries):
                async with self.dynamodb_client.client() as client:
                    response = await client.batch_write_item(RequestItems=pending)
                unprocessed = response.get("UnprocessedItems", {})
                if not unprocessed or not unprocessed.get(self.table_name):
                    break
                pending = unprocessed

            results.extend(
                self.return_entity.model_validate(
                    item.model_dump(), from_attributes=True
                )
                for item in chunk
            )
        return results

    async def batch_get_items(
        self, keys: list[DynamoKey], *, max_retries: int = 3
    ) -> list[ReturnDTO]:
        """Batch get items (auto-chunks to 100, retries UnprocessedKeys)."""
        results: list[ReturnDTO] = []

        for i in range(0, len(keys), 100):
            chunk = keys[i : i + 100]
            pending_keys = [self._serialize_key(k) for k in chunk]

            pending: dict[str, dict] = {self.table_name: {"Keys": pending_keys}}
            for _ in range(max_retries):
                async with self.dynamodb_client.client() as client:
                    response = await client.batch_get_item(RequestItems=pending)
                raw_items = response.get("Responses", {}).get(self.table_name, [])
                results.extend(self._deserialize_item(raw) for raw in raw_items)
                unprocessed = response.get("UnprocessedKeys", {})
                if not unprocessed or not unprocessed.get(self.table_name):
                    break
                pending = unprocessed
        return results

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _serialize_key(self, key: DynamoKey) -> dict[str, Any]:
        meta = self.model.__dynamo_meta__
        result: dict[str, Any] = {
            meta.partition_key_name: self._serializer.serialize(key.partition_key)
        }
        if meta.sort_key_name and key.sort_key is not None:
            result[meta.sort_key_name] = self._serializer.serialize(key.sort_key)
        return result

    def _deserialize_item(self, raw: dict[str, Any]) -> ReturnDTO:
        deserialized = {k: self._deserializer.deserialize(v) for k, v in raw.items()}
        cleaned = {k: DynamoModel._clean_value(v) for k, v in deserialized.items()}
        return self.return_entity.model_validate(cleaned)

    def _build_update_expression(
        self, data: dict[str, Any]
    ) -> tuple[str, dict[str, str], dict[str, Any]]:
        """Build SET UpdateExpression from a dict of field→value."""
        set_parts: list[str] = []
        expr_names: dict[str, str] = {}
        expr_values: dict[str, Any] = {}

        for idx, (field, value) in enumerate(data.items()):
            name_key = f"#f{idx}"
            value_key = f":v{idx}"
            expr_names[name_key] = field
            expr_values[value_key] = self._serializer.serialize(
                DynamoModel._convert_value(value)
            )
            set_parts.append(f"{name_key} = {value_key}")

        return f"SET {', '.join(set_parts)}", expr_names, expr_values

    @staticmethod
    def _encode_cursor(last_evaluated_key: dict[str, Any]) -> str:
        return base64.urlsafe_b64encode(
            json.dumps(last_evaluated_key).encode()
        ).decode()

    @staticmethod
    def _decode_cursor(cursor: str) -> dict[str, Any]:
        return json.loads(base64.urlsafe_b64decode(cursor.encode()))
