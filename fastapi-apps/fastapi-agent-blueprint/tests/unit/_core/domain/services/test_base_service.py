from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel

from src._core.application.dtos.base_response import PaginationInfo
from src._core.domain.services.base_service import BaseService
from src._core.domain.value_objects.daily_count import DailyCount


class CreateItem(BaseModel):
    name: str


class UpdateItem(BaseModel):
    name: str | None = None


class ItemDTO(BaseModel):
    id: int
    name: str


class FakeRepository:
    def __init__(self) -> None:
        self.items: dict[int, ItemDTO] = {}
        self.next_id = 1
        self.deleted: list[int] = []
        self.by_day_calls: list[tuple[datetime, str]] = []

    async def insert_data(self, entity: BaseModel) -> ItemDTO:
        item = ItemDTO(id=self.next_id, name=entity.model_dump()["name"])
        self.items[item.id] = item
        self.next_id += 1
        return item

    async def insert_datas(self, entities: Sequence[BaseModel]) -> list[ItemDTO]:
        return [await self.insert_data(entity) for entity in entities]

    async def select_datas(self, page: int, page_size: int) -> list[ItemDTO]:
        return list(self.items.values())

    async def select_data_by_id(self, data_id: int) -> ItemDTO:
        return self.items[data_id]

    async def select_datas_by_ids(self, data_ids: list[int]) -> list[ItemDTO]:
        return [self.items[data_id] for data_id in data_ids]

    async def exists_by_id(self, data_id: int) -> bool:
        return data_id in self.items

    async def exists_by_fields(
        self,
        filters: Mapping[str, Any],
        *,
        exclude_id: int | None = None,
    ) -> bool:
        return False

    async def existing_values_by_field(
        self,
        field: str,
        values: list[Any],
        *,
        exclude_id: int | None = None,
    ) -> set[Any]:
        return set()

    async def select_datas_with_count(
        self,
        page: int,
        page_size: int,
        query_filter=None,
    ) -> tuple[list[ItemDTO], int]:
        items = list(self.items.values())
        return items, len(items)

    async def update_data_by_data_id(
        self,
        data_id: int,
        entity: BaseModel,
    ) -> ItemDTO:
        item = self.items[data_id].model_copy(
            update=entity.model_dump(exclude_none=True)
        )
        self.items[data_id] = item
        return item

    async def delete_data_by_data_id(self, data_id: int) -> bool:
        self.deleted.append(data_id)
        self.items.pop(data_id, None)
        return True

    async def count_datas(self) -> int:
        return len(self.items)

    async def count_datas_by_day(
        self, *, since: datetime, column_name: str = "created_at"
    ) -> list[DailyCount]:
        self.by_day_calls.append((since, column_name))
        return [DailyCount(day=date(2026, 8, 11), count=2)]


class HookedService(BaseService[CreateItem, UpdateItem, ItemDTO]):
    def __init__(self, repository: FakeRepository) -> None:
        super().__init__(repository=repository)
        self.events: list[str] = []

    async def _validate_create(self, entity: CreateItem) -> None:
        self.events.append(f"create:{entity.name}")

    async def _validate_create_many(self, entities: list[CreateItem]) -> None:
        self.events.append(f"create_many:{len(entities)}")

    async def _validate_update(self, data_id: int, entity: UpdateItem) -> None:
        self.events.append(f"update:{data_id}")

    async def _validate_delete(self, data_id: int) -> None:
        self.events.append(f"delete:{data_id}")


async def test_base_service_default_validation_hooks_are_noop():
    service = BaseService[CreateItem, UpdateItem, ItemDTO](repository=FakeRepository())

    created = await service.create_data(CreateItem(name="one"))
    updated = await service.update_data_by_data_id(
        created.id,
        UpdateItem(name="two"),
    )
    deleted = await service.delete_data_by_data_id(created.id)

    assert updated.name == "two"
    assert deleted is True


async def test_base_service_calls_validation_hooks_for_write_paths():
    service = HookedService(repository=FakeRepository())

    created = await service.create_data(CreateItem(name="one"))
    await service.create_datas([CreateItem(name="two"), CreateItem(name="three")])
    await service.update_data_by_data_id(created.id, UpdateItem(name="updated"))
    await service.delete_data_by_data_id(created.id)

    assert service.events == [
        "create:one",
        "create_many:2",
        "update:1",
        "delete:1",
    ]


async def test_base_service_read_paths_still_return_pagination():
    service = BaseService[CreateItem, UpdateItem, ItemDTO](repository=FakeRepository())
    await service.create_data(CreateItem(name="one"))

    items, pagination = await service.get_datas(page=1, page_size=10)

    assert len(items) == 1
    assert isinstance(pagination, PaginationInfo)
    assert pagination.total_items == 1


class TestCountDatasByDayDelegation:
    """`BaseService.count_datas_by_day` is a pass-through, and the reason it
    exists is reachability: callers hold a **service**, so a repository method
    with no service counterpart cannot be used by the admin dashboard, which
    resolves `config._get_service()` and never a repository (#368).
    """

    async def test_arguments_reach_the_repository_verbatim(self) -> None:
        repo = FakeRepository()
        service = BaseService[CreateItem, UpdateItem, ItemDTO](repository=repo)

        await service.count_datas_by_day(
            since=datetime(2026, 8, 1), column_name="occurred_at"
        )

        assert repo.by_day_calls == [(datetime(2026, 8, 1), "occurred_at")]

    async def test_default_column_is_created_at(self) -> None:
        repo = FakeRepository()
        service = BaseService[CreateItem, UpdateItem, ItemDTO](repository=repo)

        await service.count_datas_by_day(since=datetime(2026, 8, 1))

        assert repo.by_day_calls == [(datetime(2026, 8, 1), "created_at")]

    async def test_repository_result_is_returned_unchanged(self) -> None:
        """No reshaping at this layer: engine normalisation and the fail-closed
        column check belong to BaseRepository (ADR 058) and must not be masked."""
        repo = FakeRepository()
        service = BaseService[CreateItem, UpdateItem, ItemDTO](repository=repo)

        rows = await service.count_datas_by_day(since=datetime(2026, 8, 1))

        assert rows == [DailyCount(day=date(2026, 8, 11), count=2)]
