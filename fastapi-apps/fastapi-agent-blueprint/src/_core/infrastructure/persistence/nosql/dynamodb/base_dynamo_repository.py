from __future__ import annotations

import asyncio
import base64
import binascii
import json
import random
from abc import ABC
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Generic, TypeVar

import structlog
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
    DynamoDBBatchIncompleteException,
    DynamoDBInvalidCursorException,
    DynamoDBInvalidLimitException,
    DynamoDBNotFoundException,
)

if TYPE_CHECKING:
    from types_aiobotocore_dynamodb.type_defs import KeysAndAttributesUnionTypeDef

_logger = structlog.stdlib.get_logger(__name__)

# Exponential base for batch retries. DynamoDB returns UnprocessedItems under
# throughput throttling, so retrying with no wait at all is the case most likely
# to fail three times in a row.
_BATCH_BACKOFF_BASE_S = 0.05

# base64url uses - and _ where standard base64 uses + and /.
_URLSAFE_TO_STANDARD = str.maketrans("-_", "+/")

# DynamoDB AttributeValue type codes. An ExclusiveStartKey is a mapping of
# attribute name to a single-entry {type_code: value} dict.
_ATTRIBUTE_TYPE_CODES = frozenset(
    {"S", "N", "B", "SS", "NS", "BS", "M", "L", "NULL", "BOOL"}
)


def _batch_backoff_delay(attempt: int) -> float:
    """Exponential backoff with jitter.

    Jitter matters here specifically: UnprocessedItems arrives under throttling,
    so several concurrent callers back off at the same moment and would
    otherwise re-collide in lockstep on every retry.
    """
    ceiling = _BATCH_BACKOFF_BASE_S * (2**attempt)
    # noqa S311: retry jitter, not a security decision.
    return ceiling * (0.5 + random.random() / 2)  # noqa: S311


def _is_dynamodb_key_map(value: object) -> bool:
    """Shape check for an ExclusiveStartKey, not a full type validation.

    Verifies the wire shape botocore expects — attribute name to a single
    ``{type_code: value}`` entry, with ``S``/``N`` carrying strings. Deeper
    per-type checking is botocore's job and would drift from it.
    """
    if not isinstance(value, dict) or not value:
        return False
    for attribute in value.values():
        if not isinstance(attribute, dict) or len(attribute) != 1:
            return False
        ((type_code, inner),) = attribute.items()
        if type_code not in _ATTRIBUTE_TYPE_CODES:
            return False
        if type_code in {"S", "N"} and not isinstance(inner, str):
            return False
    return True


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
        # `is not None`, not truthiness: limit=0 is falsy, so the bound used to
        # be dropped and the query returned a full page. DynamoDB rejects
        # Limit < 1, so an explicit error beats forwarding an invalid value.
        if limit is not None:
            if limit < 1:
                raise DynamoDBInvalidLimitException(limit)
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
            for attempt in range(max_retries):
                async with self.dynamodb_client.client() as client:
                    response = await client.batch_write_item(RequestItems=pending)
                unprocessed = response.get("UnprocessedItems", {})
                if not unprocessed or not unprocessed.get(self.table_name):
                    break
                pending = unprocessed
                # DynamoDB returns UnprocessedItems under throughput throttling,
                # which is exactly when immediate un-backed-off retries all fail
                # together. Skip the wait after the final attempt.
                if attempt < max_retries - 1:
                    await asyncio.sleep(_batch_backoff_delay(attempt))
            else:
                leftover = len(pending.get(self.table_name, []))
                _logger.error(
                    "dynamo_batch_write_unprocessed",
                    table=self.table_name,
                    unprocessed_count=leftover,
                    max_retries=max_retries,
                )
                raise DynamoDBBatchIncompleteException("batch_write_item", leftover)

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

            # `Mapping`, not `dict`: the retry loop reassigns `pending` from the
            # response's `UnprocessedKeys`, whose value type is the *output*
            # variant of this TypedDict. Feeding that back into a request is what
            # the Union type exists for, and `Mapping` is what makes the two
            # variants interchangeable here — `dict` is invariant in its value
            # type, so it would reject the reassignment.
            pending: Mapping[str, KeysAndAttributesUnionTypeDef] = {
                self.table_name: {"Keys": pending_keys}
            }
            for attempt in range(max_retries):
                async with self.dynamodb_client.client() as client:
                    response = await client.batch_get_item(RequestItems=pending)
                raw_items = response.get("Responses", {}).get(self.table_name, [])
                results.extend(self._deserialize_item(raw) for raw in raw_items)
                unprocessed = response.get("UnprocessedKeys", {})
                if not unprocessed or not unprocessed.get(self.table_name):
                    break
                pending = unprocessed
                if attempt < max_retries - 1:
                    await asyncio.sleep(_batch_backoff_delay(attempt))
            else:
                # Raising discards the reads that did succeed in this call. That
                # is the accepted trade: reads are idempotent and cheap to redo,
                # while a short list is indistinguishable from "those keys do not
                # exist" and cannot be detected by the caller at all.
                leftover = len(pending.get(self.table_name, {}).get("Keys", []))
                _logger.error(
                    "dynamo_batch_get_unprocessed",
                    table=self.table_name,
                    unprocessed_count=leftover,
                    max_retries=max_retries,
                )
                raise DynamoDBBatchIncompleteException("batch_get_item", leftover)
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
        """Decode a client-supplied pagination token.

        Guarded because the value comes straight from a query string: an
        unguarded ``binascii.Error`` / ``JSONDecodeError`` / ``UnicodeDecodeError``
        escaped as a 500, which is the wrong status and — since #17 — pages an
        operator for a malformed request. The sibling ``_column_for_field``
        already validates; this path had missed it.
        """
        try:
            # b64decode(validate=True), not urlsafe_b64decode: the urlsafe
            # variant takes no validate flag and silently ignores characters
            # outside the alphabet, so a tampered token like "e30=!!" still
            # decodes to "{}" and is accepted. Translate the two urlsafe
            # characters back, then validate.
            raw = base64.b64decode(
                cursor.translate(_URLSAFE_TO_STANDARD), validate=True
            )
            decoded = json.loads(raw)
        except (binascii.Error, ValueError) as exc:
            # json.JSONDecodeError and UnicodeDecodeError both subclass
            # ValueError; listing them separately would be redundant.
            raise DynamoDBInvalidCursorException() from exc
        if not _is_dynamodb_key_map(decoded):
            # Valid base64 and valid JSON is not enough. `{"PK": "x"}` and
            # `{"PK": {"S": 1}}` used to pass here and fail *inside* the AWS
            # call as a botocore parameter-validation error, which
            # DynamoDBClient does not translate — so a malformed token was
            # still a 500.
            raise DynamoDBInvalidCursorException()
        return decoded
