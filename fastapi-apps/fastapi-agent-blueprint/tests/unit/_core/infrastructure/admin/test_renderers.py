from datetime import datetime

from pydantic import BaseModel

from src._core.infrastructure.admin.base_admin_page import BaseAdminPage, ColumnConfig


class SampleDTO(BaseModel):
    id: int
    name: str
    password: str
    created_at: datetime


def _make_page_config() -> BaseAdminPage:
    return BaseAdminPage(
        domain_name="sample",
        display_name="Sample",
        columns=[
            ColumnConfig(field_name="id", header_name="ID", width=80),
            ColumnConfig(field_name="name", header_name="Name", searchable=True),
            ColumnConfig(field_name="password", header_name="Password", masked=True),
            ColumnConfig(field_name="created_at", header_name="Created At"),
        ],
    )


def _make_sample_dto(**overrides) -> SampleDTO:
    defaults = {
        "id": 1,
        "name": "test-user",
        "password": "secret123",
        "created_at": datetime(2025, 1, 15, 10, 30, 0),
    }
    defaults.update(overrides)
    return SampleDTO(**defaults)


class TestBuildColumnDefs:
    def test_returns_all_visible_columns(self):
        config = _make_page_config()
        defs = config.build_column_defs()
        assert len(defs) == 4
        assert defs[0]["field"] == "id"
        assert defs[1]["field"] == "name"

    def test_includes_width_when_set(self):
        config = _make_page_config()
        defs = config.build_column_defs()
        assert defs[0]["width"] == 80
        assert "width" not in defs[1]

    def test_includes_mask_formatter_for_masked_fields(self):
        config = _make_page_config()
        defs = config.build_column_defs()
        password_def = defs[2]
        assert "valueFormatter" in password_def

    def test_excludes_hidden_columns(self):
        config = BaseAdminPage(
            domain_name="t",
            display_name="T",
            columns=[
                ColumnConfig(field_name="id", header_name="ID"),
                ColumnConfig(field_name="hidden_field", header_name="H", hidden=True),
            ],
        )
        defs = config.build_column_defs()
        fields = [d["field"] for d in defs]
        assert "hidden_field" not in fields

    def test_sortable_flag_passed_through(self):
        config = BaseAdminPage(
            domain_name="t",
            display_name="T",
            columns=[
                ColumnConfig(field_name="id", header_name="ID", sortable=False),
            ],
        )
        defs = config.build_column_defs()
        assert defs[0]["sortable"] is False


class TestBuildRowData:
    def test_masks_sensitive_fields(self):
        config = _make_page_config()
        dtos = [_make_sample_dto()]
        rows = config.build_row_data(dtos, masked_fields={"password"})
        assert rows[0]["password"] == "****"

    def test_empty_masked_field_returns_empty_string(self):
        config = _make_page_config()
        dtos = [_make_sample_dto(password="")]
        rows = config.build_row_data(dtos, masked_fields={"password"})
        assert rows[0]["password"] == ""

    def test_converts_datetime_to_isoformat(self):
        config = _make_page_config()
        dtos = [_make_sample_dto()]
        rows = config.build_row_data(dtos, masked_fields=set())
        assert rows[0]["created_at"] == "2025-01-15T10:30:00"

    def test_non_masked_fields_unchanged(self):
        config = _make_page_config()
        dtos = [_make_sample_dto()]
        rows = config.build_row_data(dtos, masked_fields=set())
        assert rows[0]["id"] == 1
        assert rows[0]["name"] == "test-user"

    def test_multiple_dtos(self):
        config = _make_page_config()
        dtos = [_make_sample_dto(id=1), _make_sample_dto(id=2)]
        rows = config.build_row_data(dtos, masked_fields=set())
        assert len(rows) == 2
        assert rows[0]["id"] == 1
        assert rows[1]["id"] == 2

    def test_empty_list(self):
        config = _make_page_config()
        rows = config.build_row_data([], masked_fields=set())
        assert rows == []
