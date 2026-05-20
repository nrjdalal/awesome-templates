from __future__ import annotations

from typing import TYPE_CHECKING, Any, Generic, TypeVar

from pydantic import BaseModel

if TYPE_CHECKING:
    from src._core.domain.value_objects.cursor_page import CursorPage
    from src._core.domain.value_objects.dynamo_key import DynamoKey, SortKeyCondition

ReturnDTO = TypeVar("ReturnDTO", bound=BaseModel)


class BaseDynamoRepositoryProtocol(Generic[ReturnDTO]):
    async def put_item(self, entity: BaseModel) -> ReturnDTO: ...

    async def get_item(self, key: DynamoKey) -> ReturnDTO: ...

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
    ) -> CursorPage[ReturnDTO]: ...

    async def update_item(self, key: DynamoKey, entity: BaseModel) -> ReturnDTO: ...

    async def delete_item(self, key: DynamoKey) -> bool: ...
