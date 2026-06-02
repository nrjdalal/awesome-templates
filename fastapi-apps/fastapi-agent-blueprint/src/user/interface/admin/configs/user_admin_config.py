from src._core.infrastructure.admin.base_admin_page import (
    BaseAdminPage,
    ColumnConfig,
)

user_admin_page = BaseAdminPage(
    domain_name="user",
    display_name="User",
    icon="person",
    columns=[
        ColumnConfig(field_name="id", header_name="ID", width=80),
        ColumnConfig(field_name="username", header_name="Username", searchable=True),
        ColumnConfig(field_name="full_name", header_name="Full Name"),
        ColumnConfig(field_name="email", header_name="Email", searchable=True),
        ColumnConfig(field_name="password", header_name="Password", masked=True),
        ColumnConfig(field_name="created_at", header_name="Created At"),
        ColumnConfig(field_name="updated_at", header_name="Updated At"),
    ],
    searchable_fields=["username", "email"],
    sortable_fields=["id", "username", "created_at"],
    default_sort_field="id",
)
