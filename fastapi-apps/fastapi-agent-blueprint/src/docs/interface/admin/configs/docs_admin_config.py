from __future__ import annotations

from src._core.infrastructure.admin.base_admin_page import (
    BaseAdminPage,
    ColumnConfig,
)

docs_admin_page = BaseAdminPage(
    domain_name="docs",
    display_name="Docs",
    icon="description",
    columns=[
        ColumnConfig(field_name="id", header_name="ID", width=80),
        ColumnConfig(field_name="title", header_name="Title", searchable=True),
        ColumnConfig(field_name="source", header_name="Source"),
        ColumnConfig(field_name="chunk_count", header_name="Chunks", width=100),
        ColumnConfig(field_name="created_at", header_name="Created At"),
        ColumnConfig(field_name="updated_at", header_name="Updated At"),
    ],
    searchable_fields=["title"],
    sortable_fields=["id", "created_at"],
    default_sort_field="id",
    extra_services_config={"query": "docs_query_service"},
)
