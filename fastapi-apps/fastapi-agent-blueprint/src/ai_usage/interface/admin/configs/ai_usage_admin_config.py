from __future__ import annotations

from src._core.infrastructure.admin.base_admin_page import (
    BaseAdminPage,
    ColumnConfig,
)

ai_usage_admin_page = BaseAdminPage(
    domain_name="ai_usage",
    display_name="AI Usage",
    icon="query_stats",
    columns=[
        ColumnConfig(field_name="id", header_name="ID", width=80),
        ColumnConfig(field_name="call_id", header_name="Call ID", searchable=True),
        ColumnConfig(
            field_name="request_id", header_name="Request ID", searchable=True
        ),
        ColumnConfig(field_name="org_id", header_name="Org", searchable=True),
        ColumnConfig(field_name="agent_name", header_name="Agent", searchable=True),
        ColumnConfig(field_name="provider", header_name="Provider"),
        ColumnConfig(field_name="model", header_name="Model", searchable=True),
        ColumnConfig(field_name="status", header_name="Status", width=120),
        ColumnConfig(field_name="total_tokens", header_name="Tokens", width=120),
        ColumnConfig(field_name="requests", header_name="Requests", width=120),
        ColumnConfig(field_name="provider_cost_amount", header_name="Provider Cost"),
        ColumnConfig(field_name="provider_cost_currency", header_name="Currency"),
        ColumnConfig(field_name="provider_cost_source", header_name="Cost Source"),
        ColumnConfig(field_name="prompt_name", header_name="Prompt"),
        ColumnConfig(field_name="prompt_version", header_name="Prompt Version"),
        ColumnConfig(field_name="prompt_source", header_name="Prompt Source"),
        ColumnConfig(field_name="occurred_at", header_name="Occurred At"),
        ColumnConfig(field_name="created_at", header_name="Created At"),
    ],
    searchable_fields=["call_id", "request_id", "org_id", "agent_name", "model"],
    sortable_fields=["id", "occurred_at", "created_at", "total_tokens"],
    default_sort_field="id",
    default_sort_order="desc",
    readonly=True,
)
