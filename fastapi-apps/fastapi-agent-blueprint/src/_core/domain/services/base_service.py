from __future__ import annotations

from typing import TYPE_CHECKING, Generic, TypeVar, cast

from pydantic import BaseModel

from src._core.application.dtos.base_response import PaginationInfo
from src._core.common.pagination import make_pagination
from src._core.domain.protocols.repository_protocol import BaseRepositoryProtocol

if TYPE_CHECKING:
    from src._core.domain.value_objects.query_filter import QueryFilter

CreateDTO = TypeVar("CreateDTO", bound=BaseModel)
UpdateDTO = TypeVar("UpdateDTO", bound=BaseModel)
ReturnDTO = TypeVar("ReturnDTO", bound=BaseModel)


class BaseService(Generic[CreateDTO, UpdateDTO, ReturnDTO]):
    def __init__(self, repository: BaseRepositoryProtocol[ReturnDTO]) -> None:
        self.repository = repository

    async def create_data(self, entity: CreateDTO) -> ReturnDTO:
        await self._validate_create(entity)
        return await self.repository.insert_data(entity=entity)

    async def create_datas(self, entities: list[CreateDTO]) -> list[ReturnDTO]:
        await self._validate_create_many(entities)
        return await self.repository.insert_datas(
            entities=cast(list[BaseModel], entities)
        )

    async def get_datas(
        self,
        page: int,
        page_size: int,
        query_filter: QueryFilter | None = None,
    ) -> tuple[list[ReturnDTO], PaginationInfo]:
        datas, total_items = await self.repository.select_datas_with_count(
            page=page,
            page_size=page_size,
            query_filter=query_filter,
        )
        pagination = make_pagination(
            total_items=total_items, page=page, page_size=page_size
        )
        return datas, pagination

    async def get_data_by_data_id(self, data_id: int) -> ReturnDTO:
        return await self.repository.select_data_by_id(data_id=data_id)

    async def get_datas_by_data_ids(self, data_ids: list[int]) -> list[ReturnDTO]:
        return await self.repository.select_datas_by_ids(data_ids=data_ids)

    async def update_data_by_data_id(
        self, data_id: int, entity: UpdateDTO
    ) -> ReturnDTO:
        await self._validate_update(data_id, entity)
        return await self.repository.update_data_by_data_id(
            data_id=data_id, entity=entity
        )

    async def delete_data_by_data_id(self, data_id: int) -> bool:
        await self._validate_delete(data_id)
        return await self.repository.delete_data_by_data_id(data_id=data_id)

    async def count_datas(self) -> int:
        return await self.repository.count_datas()

    async def _validate_create(self, entity: CreateDTO) -> None:
        return None

    async def _validate_create_many(self, entities: list[CreateDTO]) -> None:
        return None

    async def _validate_update(self, data_id: int, entity: UpdateDTO) -> None:
        return None

    async def _validate_delete(self, data_id: int) -> None:
        return None
