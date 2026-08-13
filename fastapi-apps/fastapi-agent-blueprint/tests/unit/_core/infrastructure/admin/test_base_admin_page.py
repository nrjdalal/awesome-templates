from typing import Any

import pytest

from src._core.infrastructure.admin.base_admin_page import BaseAdminPage, ColumnConfig


def _make_page_config(**overrides) -> BaseAdminPage:
    defaults = {
        "domain_name": "test",
        "display_name": "Test",
        "columns": [
            ColumnConfig(field_name="id", header_name="ID"),
            ColumnConfig(field_name="name", header_name="Name", searchable=True),
            ColumnConfig(field_name="secret", header_name="Secret", masked=True),
            ColumnConfig(field_name="internal", header_name="Internal", hidden=True),
        ],
    }
    defaults.update(overrides)
    return BaseAdminPage(**defaults)


def test_get_visible_columns_excludes_hidden():
    config = _make_page_config()
    visible = config.get_visible_columns()

    field_names = [c.field_name for c in visible]
    assert "internal" not in field_names
    assert "id" in field_names
    assert "name" in field_names
    assert "secret" in field_names
    assert len(visible) == 3


def test_get_masked_field_names():
    config = _make_page_config()
    masked = config.get_masked_field_names()

    assert masked == {"secret"}


def test_get_masked_field_names_empty_when_none_masked():
    config = _make_page_config(
        columns=[ColumnConfig(field_name="id", header_name="ID")]
    )
    assert config.get_masked_field_names() == set()


def test_default_values():
    config = _make_page_config()
    assert config.icon == "list"
    assert config.page_size == 20
    assert config.readonly is True
    assert config.default_sort_field == "id"
    assert config.default_sort_order == "desc"


def test_get_service_raises_when_provider_not_set():
    config = _make_page_config()
    with pytest.raises(RuntimeError, match="service_provider not set"):
        config._get_service()


class _MinimalService:
    """The two members `AdminCrudServiceProtocol` declares, and nothing else.

    A bare `object()` was the previous sentinel. It works at runtime — the test
    only asserts identity — but `_service_provider` is typed
    `Callable[[], AdminCrudServiceProtocol]`, so an `object` provider claims the
    wiring is valid when it is not. Giving the stand-in the shape of the thing it
    stands in for keeps the identity assertion and makes the annotation true.
    """

    async def get_datas(
        self, page: int, page_size: int, query_filter: Any
    ) -> tuple[list[Any], Any]:
        raise NotImplementedError

    async def get_data_by_data_id(self, data_id: int) -> Any:
        raise NotImplementedError


def test_get_service_calls_provider():
    sentinel = _MinimalService()
    config = _make_page_config()
    config._service_provider = lambda: sentinel

    assert config._get_service() is sentinel
