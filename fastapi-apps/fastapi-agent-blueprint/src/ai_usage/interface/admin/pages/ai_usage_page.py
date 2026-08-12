from __future__ import annotations

from typing import Protocol, cast

from nicegui import ui

from src._core.infrastructure.admin import components as c
from src._core.infrastructure.admin.auth import require_auth
from src._core.infrastructure.admin.base_admin_page import BaseAdminPage
from src._core.infrastructure.admin.error_handler import admin_error_boundary
from src._core.infrastructure.admin.layout import admin_layout
from src.ai_usage.domain.dtos.ai_usage_dto import (
    AiUsageByOrgDTO,
    AiUsageSummaryDTO,
)
from src.ai_usage.interface.admin.configs.ai_usage_admin_config import (
    ai_usage_admin_page,
)

# page_configs is injected by bootstrap_admin() after discovery
page_configs: list[BaseAdminPage] = []


class _UsageSummaryService(Protocol):
    """The one method this page needs, declared where it is needed.

    ``BaseAdminPage._get_service()`` returns ``AdminCrudServiceProtocol``, which
    is deliberately scoped to what ``BaseAdminPage`` itself uses — so a
    domain-specific reader like ``get_usage_summary`` is not on it, and calling it
    is an attribute error to a type checker.

    A narrow local Protocol rather than a ``cast`` to ``AiUsageService``: admin
    pages must not import domain services (architecture-review-checklist §7,
    security-checklist §2), and widening the shared CRUD protocol would couple it
    to one domain's needs. Declaring the return types also means the field access
    below is checked rather than untyped.
    """

    async def get_usage_summary(
        self,
    ) -> tuple[AiUsageSummaryDTO, list[AiUsageByOrgDTO]]: ...


@ui.page("/admin/ai_usage")
@admin_error_boundary(context="ai_usage_list")
async def ai_usage_list_page(page: int = 1, search: str = "") -> None:
    session = await require_auth(page_key="ai_usage")
    if session is None:
        return
    admin_layout(page_configs, current_domain="ai_usage", session=session)
    await ai_usage_admin_page.render_list(page=page, search=search)


@ui.page("/admin/ai_usage/summary")
@admin_error_boundary(context="ai_usage_summary")
async def ai_usage_summary_page() -> None:
    session = await require_auth(page_key="ai_usage")
    if session is None:
        return
    admin_layout(page_configs, current_domain="ai_usage", session=session)
    c.page_header("AI Usage Summary")

    try:
        service = cast(_UsageSummaryService, ai_usage_admin_page._get_service())
        summary, by_org = await service.get_usage_summary()
    except Exception as exc:  # noqa: BLE001 - delegated to AdminErrorHandler
        await c.report_error(exc, context="ai_usage_summary")
        return

    with ui.row().classes("q-gutter-md q-mb-md"):
        c.stat_card("Calls", summary.call_count)
        c.stat_card("Requests", summary.request_count)
        c.stat_card("Tokens", summary.total_tokens)
        c.stat_card("Input", summary.input_tokens)
        c.stat_card("Output", summary.output_tokens)

    rows = [item.model_dump() for item in by_org]
    c.data_grid(
        [
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
        rows,
        compact=True,
    )


@ui.page("/admin/ai_usage/{record_id}")
@admin_error_boundary(context="ai_usage_detail")
async def ai_usage_detail_page(record_id: int) -> None:
    session = await require_auth(page_key="ai_usage")
    if session is None:
        return
    admin_layout(page_configs, current_domain="ai_usage", session=session)
    await ai_usage_admin_page.render_detail(record_id=record_id)
