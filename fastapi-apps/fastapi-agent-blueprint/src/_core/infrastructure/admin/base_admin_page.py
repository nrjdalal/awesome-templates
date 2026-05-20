from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from nicegui import ui

from src._core.domain.protocols.admin_service_protocol import AdminCrudServiceProtocol
from src._core.domain.value_objects.query_filter import QueryFilter
from src._core.exceptions.base_exception import BaseCustomException

if TYPE_CHECKING:
    from src._core.application.dtos.base_response import PaginationInfo

logger = logging.getLogger(__name__)


@dataclass
class ColumnConfig:
    """Column configuration for admin CRUD table."""

    field_name: str
    header_name: str
    sortable: bool = True
    searchable: bool = False
    hidden: bool = False
    masked: bool = False
    width: int | None = None


@dataclass
class BaseAdminPage:
    """Base admin page with Template Method rendering.

    Domains create an instance for standard CRUD pages.
    For custom rendering, subclass and override hook methods.
    """

    domain_name: str
    display_name: str
    icon: str = "list"
    columns: list[ColumnConfig] = field(default_factory=list)
    searchable_fields: list[str] = field(default_factory=list)
    sortable_fields: list[str] = field(default_factory=list)
    default_sort_field: str = "id"
    default_sort_order: str = "desc"
    page_size: int = 20
    readonly: bool = True
    # Declare extra services by alias → container attr name.
    # Bootstrap resolves each by attr name from the domain container and stores
    # the callable in ``_extra_services``. Use ``_get_extra_service(alias)`` to
    # retrieve them in page handlers.
    extra_services_config: dict[str, str] = field(default_factory=dict, repr=False)
    _service_provider: Callable[[], AdminCrudServiceProtocol] | None = field(
        default=None, repr=False
    )
    _extra_services: dict[str, Callable[[], Any]] = field(
        default_factory=dict, repr=False
    )

    # ── Config helpers ──

    def get_visible_columns(self) -> list[ColumnConfig]:
        return [c for c in self.columns if not c.hidden]

    def get_masked_field_names(self) -> set[str]:
        return {c.field_name for c in self.columns if c.masked}

    def _get_service(self) -> AdminCrudServiceProtocol:
        """Resolve service from the provider injected by bootstrap."""
        if self._service_provider is None:
            raise RuntimeError(
                f"service_provider not set for '{self.domain_name}' admin page. "
                "Was bootstrap_admin() called?"
            )
        return self._service_provider()

    def _get_extra_service(self, alias: str) -> Any:
        """Resolve an extra service by alias (declared in extra_services_config)."""
        provider = self._extra_services.get(alias)
        if provider is None:
            raise RuntimeError(
                f"Extra service '{alias}' not wired for '{self.domain_name}' admin page. "
                "Declare it in extra_services_config and ensure bootstrap ran."
            )
        return provider()

    # ── Template Methods ──

    async def render_list(self, page: int = 1, search: str = "") -> None:
        """Template method: render paginated list view.

        Override individual hook methods to customize rendering.
        """
        try:
            dtos, pagination = await self._fetch_list_data(page, search)
        except BaseCustomException as e:
            logger.warning("Admin list load failed: %s", e)
            ui.notify(e.message, type="negative")
            return
        except Exception:
            logger.exception(
                "Unexpected error loading admin list for %s", self.domain_name
            )
            ui.notify("Failed to load data. Please try again later.", type="negative")
            return

        self.render_list_header()
        self.render_search_bar(search)
        self.render_list_summary(pagination)
        self.render_grid(dtos)
        self.render_pagination(pagination, search)

    async def render_detail(self, record_id: int) -> None:
        """Template method: render single-record detail view.

        Override individual hook methods to customize rendering.
        """
        try:
            dto = await self._fetch_detail_data(record_id)
        except BaseCustomException as e:
            logger.warning("Admin detail load failed: %s", e)
            ui.notify(e.message, type="negative")
            self._render_back_button()
            return
        except Exception:
            logger.exception(
                "Unexpected error loading detail for %s #%s",
                self.domain_name,
                record_id,
            )
            ui.notify("Failed to load record. Please try again later.", type="negative")
            self._render_back_button()
            return

        self.render_detail_header(record_id)
        self.render_detail_card(dto)

    # ── Data fetching (overridable) ──

    async def _fetch_list_data(self, page: int, search: str):
        """Fetch paginated list data. Override for custom filtering/aggregation."""
        service = self._get_service()
        query_filter = QueryFilter(
            sort_field=self.default_sort_field,
            sort_order=self.default_sort_order,
            search_query=search or None,
            search_fields=self.searchable_fields if search else None,
        )
        return await service.get_datas(
            page=page, page_size=self.page_size, query_filter=query_filter
        )

    async def _fetch_detail_data(self, record_id: int):
        """Fetch single record. Override for custom data source."""
        service = self._get_service()
        return await service.get_data_by_data_id(data_id=record_id)

    # ── List page hooks ──

    def render_list_header(self) -> None:
        """Hook: render list page heading."""
        ui.label(f"{self.display_name} Management").classes("text-h5 q-mb-md")

    def render_search_bar(self, search: str) -> None:
        """Hook: render search input if searchable_fields configured."""
        if not self.searchable_fields:
            return

        field_labels = ", ".join(self.searchable_fields)

        def _on_search(e) -> None:
            query = e.value.strip() if e.value else ""
            params = f"?search={query}" if query else ""
            ui.navigate.to(f"/admin/{self.domain_name}{params}")

        ui.input(
            placeholder=f"Search by {field_labels}...",
            value=search,
            on_change=lambda: None,
        ).on("keydown.enter", _on_search).props("outlined dense clearable").classes(
            "w-80 q-mb-sm"
        )

    def render_list_summary(self, pagination: PaginationInfo) -> None:
        """Hook: render total/page summary above grid."""
        with ui.row().classes("items-center q-mb-sm"):
            ui.label(
                f"Total: {pagination.total_items} | "
                f"Page {pagination.current_page} / {pagination.total_pages}"
            ).classes("text-caption")

    def render_grid(self, dtos: list) -> None:
        """Hook: render AG Grid table."""
        column_defs = self.build_column_defs()
        masked_fields = self.get_masked_field_names()
        row_data = self.build_row_data(dtos, masked_fields)

        grid = (
            ui.aggrid(
                {
                    "columnDefs": column_defs,
                    "rowData": row_data,
                    "rowSelection": {"mode": "singleRow"},
                    "defaultColDef": {"resizable": True, "filter": True},
                }
            )
            .classes("w-full")
            .style("height: 600px")
        )

        grid.on(
            "cellClicked",
            lambda e: ui.navigate.to(
                f"/admin/{self.domain_name}/{e.args['data']['id']}"
            ),
        )

    def render_pagination(self, pagination: PaginationInfo, search: str) -> None:
        """Hook: render prev/next pagination buttons."""

        def _build_page_url(target_page: int) -> str:
            params = f"page={target_page}"
            if search:
                params += f"&search={search}"
            return f"/admin/{self.domain_name}?{params}"

        with ui.row().classes("items-center q-mt-md q-gutter-sm"):
            ui.button(
                "Previous",
                on_click=lambda: ui.navigate.to(
                    _build_page_url(pagination.previous_page)
                ),
            ).props("flat" if pagination.has_previous else "flat disable")
            ui.label(f"{pagination.current_page} / {pagination.total_pages}")
            ui.button(
                "Next",
                on_click=lambda: ui.navigate.to(_build_page_url(pagination.next_page)),
            ).props("flat" if pagination.has_next else "flat disable")

    # ── Detail page hooks ──

    def render_detail_header(self, record_id: int) -> None:
        """Hook: render detail page heading with back button."""
        with ui.row().classes("items-center q-mb-md q-gutter-sm"):
            ui.button(
                icon="arrow_back",
                on_click=lambda: ui.navigate.to(f"/admin/{self.domain_name}"),
            ).props("flat round")
            ui.label(f"{self.display_name} #{record_id}").classes("text-h5")

    def render_detail_card(self, dto) -> None:
        """Hook: render detail card with all fields."""
        masked_fields = self.get_masked_field_names()
        data = dto.model_dump()

        with ui.card().classes("w-full"):
            for col in self.columns:
                value = data.get(col.field_name, "")
                if col.field_name in masked_fields:
                    display_value = "****" if value else ""
                elif hasattr(value, "isoformat"):
                    display_value = value.isoformat()
                else:
                    display_value = str(value) if value is not None else ""

                with ui.row().classes("items-center q-py-xs"):
                    ui.label(col.header_name).classes("text-weight-bold").style(
                        "width: 160px"
                    )
                    ui.label(display_value)

    # ── Data transformation helpers ──

    def build_column_defs(self) -> list[dict]:
        """Build AG Grid column definitions. Override to customize grid columns."""
        column_defs = []
        for col in self.get_visible_columns():
            col_def: dict = {
                "headerName": col.header_name,
                "field": col.field_name,
                "sortable": col.sortable,
            }
            if col.width:
                col_def["width"] = col.width
            if col.masked:
                col_def["valueFormatter"] = "value ? '****' : ''"
            column_defs.append(col_def)
        return column_defs

    def build_row_data(self, dtos: list, masked_fields: set[str]) -> list[dict]:
        """Build row data from DTOs. Override to customize row transformation."""
        rows = []
        for dto in dtos:
            row = dto.model_dump()
            for key, value in row.items():
                if key in masked_fields:
                    row[key] = "****" if value else ""
                elif hasattr(value, "isoformat"):
                    row[key] = value.isoformat()
            rows.append(row)
        return rows

    # ── Private utilities ──

    def _render_back_button(self) -> None:
        """Render back-to-list button (used in error paths)."""
        ui.button(
            "Back to list",
            on_click=lambda: ui.navigate.to(f"/admin/{self.domain_name}"),
        ).props("flat")
