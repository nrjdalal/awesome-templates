"""``/admin/audit-log`` query UI (#206 Phase 2).

Operator surface for the audit log persisted by #196 Phase 1: a filter bar
(username, action, domain, result, date range) + paginated AG Grid summary
list + row-click detail dialog with before/after JSON viewer + correlation
ID copy button.

This page deliberately does NOT call ``AuditLogger.log`` itself — viewing the
audit log is not an event we want to write into the audit log (self-loop).
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from nicegui import ui

from src._core.infrastructure.admin.audit import (
    AdminAction,
    AuditLogDTO,
    AuditLogFilter,
    AuditLogSummaryDTO,
    AuditResult,
)
from src._core.infrastructure.admin.audit.logger import get_audit_repository
from src._core.infrastructure.admin.auth import require_auth
from src._core.infrastructure.admin.base_admin_page import BaseAdminPage
from src._core.infrastructure.admin.error_handler import admin_error_boundary
from src._core.infrastructure.admin.layout import admin_layout, button_loading

# Injected by bootstrap_admin() after discovery (mirrors accounts.py).
page_configs: list[BaseAdminPage] = []

_PAGE_SIZE = 50


@ui.page("/admin/audit-log")
@admin_error_boundary(context="audit_log")
async def audit_log_page() -> None:
    session = await require_auth(page_key="audit_log")
    if session is None:
        return

    admin_layout(page_configs, current_domain="audit_log", session=session)
    ui.label("Audit Log").classes("text-h5 q-mb-md")

    # Mutable page-state shared across the filter callbacks. Kept on a dict
    # (not nonlocal scalars) so each closure can read the current value.
    state: dict[str, Any] = {"page": 1, "total": 0}

    # ── Filter bar ──────────────────────────────────────────────────────────
    with ui.row().classes("q-gutter-md q-mb-md items-end"):
        username_input = (
            ui.input("Username contains").props("outlined dense").classes("w-40")
        )
        action_select = (
            ui.select(
                {a.value: a.value for a in AdminAction},
                label="Action",
                multiple=True,
                value=[],
            )
            .props("outlined dense use-chips")
            .classes("w-56")
        )
        domain_input = (
            ui.input("Domain (comma-sep)").props("outlined dense").classes("w-44")
        )
        result_toggle = ui.toggle(
            {"": "All", "SUCCESS": "Success", "FAILURE": "Failure"}, value=""
        )
        since_input = ui.input("Since (ISO)").props("outlined dense").classes("w-44")
        until_input = ui.input("Until (ISO)").props("outlined dense").classes("w-44")
        apply_btn = ui.button("Apply", on_click=lambda: _apply()).props("color=primary")

    grid_container = ui.column().classes("w-full")
    pagination_container = ui.row().classes("q-gutter-sm items-center q-mt-sm")

    def _build_filter() -> AuditLogFilter:
        actions = tuple(AdminAction(a) for a in (action_select.value or []))
        domains = tuple(
            d.strip() for d in (domain_input.value or "").split(",") if d.strip()
        )
        return AuditLogFilter(
            username_like=(username_input.value or None),
            actions=actions,
            domains=domains,
            result=AuditResult(result_toggle.value) if result_toggle.value else None,
            since=_parse_iso(since_input.value),
            until=_parse_iso(until_input.value),
        )

    async def _refresh() -> None:
        async with button_loading(apply_btn):
            repo = get_audit_repository()
            rows, total = await repo.list_filtered(
                _build_filter(), page=state["page"], page_size=_PAGE_SIZE
            )
        state["total"] = total
        grid_container.clear()
        pagination_container.clear()
        with grid_container:
            _render_grid(rows, _show_detail)
        with pagination_container:
            _render_pagination(state, _go_prev, _go_next)

    async def _apply() -> None:
        state["page"] = 1
        await _refresh()

    async def _go_prev() -> None:
        if state["page"] > 1:
            state["page"] -= 1
            await _refresh()

    async def _go_next() -> None:
        max_page = max(1, (state["total"] + _PAGE_SIZE - 1) // _PAGE_SIZE)
        if state["page"] < max_page:
            state["page"] += 1
            await _refresh()

    async def _show_detail(audit_id: int) -> None:
        repo = get_audit_repository()
        dto = await repo.get_by_id(audit_id)
        if dto is None:
            ui.notify("Audit entry not found", type="warning")
            return
        _open_detail_dialog(dto)

    await _refresh()


# ── Helpers ─────────────────────────────────────────────────────────────────


def _parse_iso(value: str | None) -> datetime | None:
    """Best-effort ISO-8601 parse; returns ``None`` on invalid / empty input."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        ui.notify(f"Invalid date format: {value}", type="warning")
        return None


def _render_grid(
    rows: list[AuditLogSummaryDTO],
    show_detail_cb,
) -> None:
    row_data = [r.model_dump(mode="json") for r in rows]
    grid = (
        ui.aggrid(
            {
                "columnDefs": [
                    {"headerName": "Time (UTC)", "field": "created_at", "width": 200},
                    {"headerName": "User", "field": "admin_username", "width": 140},
                    {"headerName": "Action", "field": "action", "width": 160},
                    {"headerName": "Domain", "field": "domain", "width": 100},
                    {"headerName": "Record", "field": "record_id", "width": 100},
                    {"headerName": "Result", "field": "result", "width": 100},
                    {"headerName": "Reason", "field": "failure_reason", "width": 180},
                    {"headerName": "IP", "field": "ip_address", "width": 130},
                ],
                "rowData": row_data,
                "defaultColDef": {"resizable": True, "sortable": True},
                "rowSelection": "single",
            }
        )
        .classes("w-full")
        .style("height: 480px")
    )

    async def _on_row_clicked(event) -> None:
        audit_id = event.args.get("data", {}).get("id")
        if isinstance(audit_id, int):
            await show_detail_cb(audit_id)

    grid.on("rowClicked", _on_row_clicked)


def _render_pagination(state: dict[str, Any], on_prev, on_next) -> None:
    total = state["total"]
    page = state["page"]
    max_page = max(1, (total + _PAGE_SIZE - 1) // _PAGE_SIZE)

    prev_btn = ui.button("◀ Prev", on_click=on_prev).props("flat")
    if page <= 1:
        prev_btn.props("disable")
    ui.label(f"Page {page} of {max_page} • {total} total").classes("text-caption")
    next_btn = ui.button("Next ▶", on_click=on_next).props("flat")
    if page >= max_page:
        next_btn.props("disable")


def _open_detail_dialog(dto: AuditLogDTO) -> None:
    with ui.dialog() as dlg, ui.card().style("width: 800px; max-width: 95vw"):
        ui.label(f"#{dto.id} · {dto.action.value} · {dto.result.value}").classes(
            "text-h6"
        )
        created_iso = dto.created_at.isoformat() if dto.created_at else "—"
        ui.label(f"{dto.admin_username} · {created_iso}").classes(
            "text-caption text-grey-7 q-mb-sm"
        )
        if dto.correlation_id:
            with ui.row().classes("items-center q-gutter-sm q-mb-sm"):
                ui.label(f"Correlation: {dto.correlation_id}").classes("text-caption")
                ui.button(
                    "Copy",
                    on_click=lambda cid=dto.correlation_id: ui.run_javascript(
                        f"navigator.clipboard.writeText({json.dumps(cid)})"
                    ),
                ).props("flat dense size=sm")
        if dto.ip_address:
            ui.label(f"IP: {dto.ip_address}").classes("text-caption")
        if dto.record_id:
            ui.label(f"Record: {dto.record_id}").classes("text-caption")
        if dto.failure_reason:
            ui.label(f"Failure reason: {dto.failure_reason}").classes(
                "text-negative text-caption q-mb-sm"
            )
        ui.separator()
        with ui.row().classes("w-full q-gutter-md q-mt-sm"):
            with ui.column().classes("col"):
                ui.label("Before").classes("text-subtitle2")
                ui.code(
                    _safe_json(dto.before_state) or "(none)", language="json"
                ).classes("w-full")
            with ui.column().classes("col"):
                ui.label("After").classes("text-subtitle2")
                ui.code(
                    _safe_json(dto.after_state) or "(none)", language="json"
                ).classes("w-full")
        ui.button("Close", on_click=dlg.close).props("color=primary").classes("q-mt-md")
    dlg.open()


def _safe_json(value: dict | None) -> str | None:
    if value is None:
        return None
    return json.dumps(value, indent=2, ensure_ascii=False)
