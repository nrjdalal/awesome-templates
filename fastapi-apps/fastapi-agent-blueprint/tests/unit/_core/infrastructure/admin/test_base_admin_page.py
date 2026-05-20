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


def test_get_service_calls_provider():
    sentinel = object()
    config = _make_page_config()
    config._service_provider = lambda: sentinel

    assert config._get_service() is sentinel
