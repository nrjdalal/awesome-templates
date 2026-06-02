from __future__ import annotations

from nicegui import ui

from src._core.infrastructure.admin.auth import require_auth
from src._core.infrastructure.admin.base_admin_page import BaseAdminPage
from src._core.infrastructure.admin.error_handler import (
    AdminErrorHandler,
    admin_error_boundary,
)
from src._core.infrastructure.admin.layout import admin_layout, button_loading
from src._core.infrastructure.admin.theme import AdminClasses
from src.docs.interface.admin.configs.docs_admin_config import docs_admin_page

# page_configs is injected by bootstrap_admin() after discovery
page_configs: list[BaseAdminPage] = []


@ui.page("/admin/docs")
@admin_error_boundary(context="docs_list")
async def docs_list_page(page: int = 1, search: str = "") -> None:
    session = await require_auth(page_key="docs")
    if session is None:
        return
    admin_layout(page_configs, current_domain="docs", session=session)
    await docs_admin_page.render_list(page=page, search=search)


@ui.page("/admin/docs/query")
@admin_error_boundary(context="docs_query")
async def docs_query_page() -> None:
    session = await require_auth(page_key="docs")
    if session is None:
        return
    admin_layout(page_configs, current_domain="docs", session=session)
    ui.label("Docs Query Playground").classes("text-h5 q-mb-md")

    question_input = (
        ui.textarea(
            label="Question",
            placeholder="Ask a question about your ingested documents...",
        )
        .props("outlined autogrow")
        .classes("w-full")
    )
    top_k_input = (
        ui.number(label="top_k", value=5, min=1, max=50, step=1)
        .props("outlined dense")
        .classes("w-40")
    )

    answer_card = ui.card().classes(f"w-full q-mt-md {AdminClasses.HIDDEN}")

    async def _run_query() -> None:
        question = (question_input.value or "").strip()
        if not question:
            ui.notify("Question is required", type="warning")
            return
        async with button_loading(ask_btn):
            try:
                service = docs_admin_page._get_extra_service("query")
                answer, retrieved_count = await service.answer_question(
                    question=question, top_k=int(top_k_input.value or 5)
                )
            except Exception as exc:  # noqa: BLE001 - delegated to AdminErrorHandler
                await AdminErrorHandler.handle(exc, context="docs_query")
                return

        answer_card.clear()
        answer_card.classes(remove=AdminClasses.HIDDEN)
        with answer_card:
            ui.label("Answer").classes("text-subtitle1 text-weight-bold")
            ui.label(answer.answer).classes(AdminClasses.PRE)
            ui.separator().classes("q-my-md")
            ui.label("Citations (" + str(retrieved_count) + " retrieved)").classes(
                "text-subtitle1 text-weight-bold"
            )
            if not answer.citations:
                ui.label("(no citations)").classes("text-caption")
            for citation in answer.citations:
                with ui.card().classes("q-mb-sm"):
                    ui.label(
                        "["
                        + citation.source_title
                        + "] (source #"
                        + str(citation.source_id)
                        + ")"
                    ).classes("text-weight-bold")
                    ui.label(citation.excerpt).classes("text-caption")
                    if citation.distance is not None:
                        ui.label("distance: " + f"{citation.distance:.4f}").classes(
                            "text-caption"
                        )

    ask_btn = ui.button("Ask", on_click=_run_query).props("color=primary")


@ui.page("/admin/docs/{record_id}")
@admin_error_boundary(context="docs_detail")
async def docs_detail_page(record_id: int) -> None:
    session = await require_auth(page_key="docs")
    if session is None:
        return
    admin_layout(page_configs, current_domain="docs", session=session)
    await docs_admin_page.render_detail(record_id=record_id)
