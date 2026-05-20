from __future__ import annotations

import logging

from nicegui import ui

from src._core.infrastructure.admin.auth import require_auth
from src._core.infrastructure.admin.base_admin_page import BaseAdminPage
from src._core.infrastructure.admin.layout import admin_layout
from src.ai_usage.interface.admin.configs.ai_usage_admin_config import (
    ai_usage_admin_page,
)

logger = logging.getLogger(__name__)

# page_configs is injected by bootstrap_admin() after discovery
page_configs: list[BaseAdminPage] = []


@ui.page("/admin/ai_usage")
async def ai_usage_list_page(page: int = 1, search: str = "") -> None:
    if not await require_auth():
        return
    admin_layout(page_configs, current_domain="ai_usage")
    await ai_usage_admin_page.render_list(page=page, search=search)


@ui.page("/admin/ai_usage/summary")
async def ai_usage_summary_page() -> None:
    if not await require_auth():
        return
    admin_layout(page_configs, current_domain="ai_usage")
    ui.label("AI Usage Summary").classes("text-h5 q-mb-md")

    try:
        service = ai_usage_admin_page._get_service()
        summary, by_org = await service.get_usage_summary()
    except Exception:
        logger.exception("AI usage admin summary failed")
        ui.notify("Failed to load AI usage summary", type="negative")
        return

    with ui.row().classes("q-gutter-md q-mb-md"):
        _summary_tile("Calls", summary.call_count)
        _summary_tile("Requests", summary.request_count)
        _summary_tile("Tokens", summary.total_tokens)
        _summary_tile("Input", summary.input_tokens)
        _summary_tile("Output", summary.output_tokens)

    rows = [item.model_dump() for item in by_org]
    ui.aggrid(
        {
            "columnDefs": [
                {"headerName": "Org", "field": "org_id"},
                {"headerName": "Calls", "field": "call_count"},
                {"headerName": "Requests", "field": "request_count"},
                {"headerName": "Tokens", "field": "total_tokens"},
                {"headerName": "Input", "field": "input_tokens"},
                {"headerName": "Output", "field": "output_tokens"},
                {"headerName": "Cache Read", "field": "cache_read_tokens"},
                {"headerName": "Cache Write", "field": "cache_write_tokens"},
                {"headerName": "Reasoning", "field": "reasoning_tokens"},
            ],
            "rowData": rows,
            "defaultColDef": {"resizable": True, "sortable": True},
        }
    ).classes("w-full").style("height: 420px")


@ui.page("/admin/ai_usage/{record_id}")
async def ai_usage_detail_page(record_id: int) -> None:
    if not await require_auth():
        return
    admin_layout(page_configs, current_domain="ai_usage")
    await ai_usage_admin_page.render_detail(record_id=record_id)


def _summary_tile(label: str, value: int) -> None:
    with ui.card().classes("q-pa-md"):
        ui.label(label).classes("text-caption")
        ui.label(str(value)).classes("text-h6")
