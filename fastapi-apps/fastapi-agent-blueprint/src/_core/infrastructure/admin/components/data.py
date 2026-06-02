"""Data-display builders for the admin design system (#193 follow-up).

``data_grid`` is the single place that turns column defs + row data into an
AG Grid with the admin theme + shared defaults. Masking / formatting / column
selection stay in the caller (e.g. BaseAdminPage) — this builder only renders.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from nicegui import ui

from src._core.infrastructure.admin.theme import AdminClasses, AdminMetrics

_SHARED_DEFAULT_COL_DEF: dict[str, Any] = {
    "resizable": True,
    "filter": True,
    "sortable": True,
}


def data_grid(
    column_defs: list[dict],
    row_data: list[dict],
    *,
    compact: bool = False,
    row_click_to: Callable[[dict], str] | None = None,
    on_cell_click: Callable[[Any], Any] | None = None,
    on_row_click: Callable[[Any], Awaitable[None]] | Callable[[Any], Any] | None = None,
    default_col_def: dict | None = None,
    selection: str = "single",
) -> ui.aggrid:
    """Render an AG Grid with the admin theme class + shared defaults.

    Click handling (all optional, async-safe):
    - ``row_click_to``: row dict → route; navigates on cellClicked (the common
      list→detail case).
    - ``on_cell_click`` / ``on_row_click``: raw handlers (sync or async) for the
      cellClicked / rowClicked events (e.g. opening a detail dialog).
    """
    col_def = {**_SHARED_DEFAULT_COL_DEF, **(default_col_def or {})}
    grid = ui.aggrid(
        {
            "columnDefs": column_defs,
            "rowData": row_data,
            "rowSelection": {"mode": "singleRow"}
            if selection == "single"
            else selection,
            "rowHeight": AdminMetrics.GRID_ROW_HEIGHT,
            "defaultColDef": col_def,
        }
    ).classes(f"w-full {AdminClasses.GRID_COMPACT if compact else AdminClasses.GRID}")

    if row_click_to is not None:
        grid.on(
            "cellClicked",
            lambda e: ui.navigate.to(row_click_to(e.args["data"])),
        )
    elif on_cell_click is not None:
        grid.on("cellClicked", on_cell_click)
    if on_row_click is not None:
        grid.on("rowClicked", on_row_click)
    return grid


def pagination(
    *,
    current: int,
    total_pages: int,
    on_prev: Callable[..., Any],
    on_next: Callable[..., Any],
) -> ui.row:
    """Prev / page-label / next row, right-aligned, with disabled end states."""
    with ui.row().classes(
        f"items-center q-mt-md q-gutter-sm {AdminClasses.PAGINATION}"
    ) as row:
        prev_btn = ui.button("Previous", on_click=on_prev).props("flat")
        if current <= 1:
            prev_btn.props("disable")
        ui.label(f"{current} / {total_pages}")
        next_btn = ui.button("Next", on_click=on_next).props("flat")
        if current >= total_pages:
            next_btn.props("disable")
    return row
