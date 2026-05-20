from __future__ import annotations

from typing import TYPE_CHECKING, Generic, TypeVar

from pydantic import BaseModel

from src._core.domain.protocols.dynamo_repository_protocol import (
    BaseDynamoRepositoryProtocol,
)

if TYPE_CHECKING:
    from src._core.domain.value_objects.cursor_page import CursorPage
    from src._core.domain.value_objects.dynamo_key import DynamoKey, SortKeyCondition

CreateDTO = TypeVar("CreateDTO", bound=BaseModel)
UpdateDTO = TypeVar("UpdateDTO", bound=BaseModel)
ReturnDTO = TypeVar("ReturnDTO", bound=BaseModel)


class BaseDynamoService(Generic[CreateDTO, UpdateDTO, ReturnDTO]):
    """Service base for DynamoDB domains.

    Parallel to ``BaseService`` but uses DynamoDB access patterns
    (composite keys, cursor pagination).
    """

    def __init__(self, repository: BaseDynamoRepositoryProtocol[ReturnDTO]) -> None:
        self.repository = repository

    async def create_item(self, entity: CreateDTO) -> ReturnDTO:
        return await self.repository.put_item(entity=entity)

    async def get_item(self, key: DynamoKey) -> ReturnDTO:
        return await self.repository.get_item(key=key)

    async def query_items(
        self,
        partition_key_value: str,
        sort_key_condition: SortKeyCondition | None = None,
        index_name: str | None = None,
        limit: int | None = None,
        cursor: str | None = None,
        scan_forward: bool = True,
    ) -> CursorPage[ReturnDTO]:
        return await self.repository.query_items(
            partition_key_value=partition_key_value,
            sort_key_condition=sort_key_condition,
            index_name=index_name,
            limit=limit,
            cursor=cursor,
            scan_forward=scan_forward,
        )

    async def update_item(self, key: DynamoKey, entity: UpdateDTO) -> ReturnDTO:
        return await self.repository.update_item(key=key, entity=entity)

    async def delete_item(self, key: DynamoKey) -> bool:
        return await self.repository.delete_item(key=key)
