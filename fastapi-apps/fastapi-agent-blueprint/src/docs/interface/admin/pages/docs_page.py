from __future__ import annotations

import logging

from nicegui import ui

from src._core.infrastructure.admin.auth import require_auth
from src._core.infrastructure.admin.base_admin_page import BaseAdminPage
from src._core.infrastructure.admin.layout import admin_layout
from src.docs.interface.admin.configs.docs_admin_config import docs_admin_page

logger = logging.getLogger(__name__)

# page_configs is injected by bootstrap_admin() after discovery
page_configs: list[BaseAdminPage] = []


@ui.page("/admin/docs")
async def docs_list_page(page: int = 1, search: str = "") -> None:
    if not await require_auth():
        return
    admin_layout(page_configs, current_domain="docs")
    await docs_admin_page.render_list(page=page, search=search)


@ui.page("/admin/docs/query")
async def docs_query_page() -> None:
    if not await require_auth():
        return
    admin_layout(page_configs, current_domain="docs")
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

    answer_card = ui.card().classes("w-full q-mt-md").style("display: none")

    async def _run_query() -> None:
        question = (question_input.value or "").strip()
        if not question:
            ui.notify("Question is required", type="warning")
            return
        try:
            service = docs_admin_page._get_extra_service("query")
            answer, retrieved_count = await service.answer_question(
                question=question, top_k=int(top_k_input.value or 5)
            )
        except Exception as exc:
            logger.exception("Docs admin query failed")
            ui.notify(f"Query failed: {exc}", type="negative")
            return

        answer_card.clear()
        answer_card.style("display: block")
        with answer_card:
            ui.label("Answer").classes("text-subtitle1 text-weight-bold")
            ui.label(answer.answer).style("white-space: pre-wrap")
            ui.separator().classes("q-my-md")
            ui.label(f"Citations ({retrieved_count} retrieved)").classes(
                "text-subtitle1 text-weight-bold"
            )
            if not answer.citations:
                ui.label("(no citations)").classes("text-caption")
            for citation in answer.citations:
                with ui.card().classes("q-mb-sm"):
                    ui.label(
                        f"[{citation.source_title}] (source #{citation.source_id})"
                    ).classes("text-weight-bold")
                    ui.label(citation.excerpt).classes("text-caption")
                    if citation.distance is not None:
                        ui.label(f"distance: {citation.distance:.4f}").classes(
                            "text-caption"
                        )

    ui.button("Ask", on_click=_run_query).props("color=primary")


@ui.page("/admin/docs/{record_id}")
async def docs_detail_page(record_id: int) -> None:
    if not await require_auth():
        return
    admin_layout(page_configs, current_domain="docs")
    await docs_admin_page.render_detail(record_id=record_id)
