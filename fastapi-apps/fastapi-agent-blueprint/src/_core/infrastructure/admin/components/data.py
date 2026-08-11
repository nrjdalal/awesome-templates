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

# Measured on AG Grid v33 quartz in the NiceGUI embed at our ``rowHeight``:
# ``.ag-header`` is 49px and the root wrapper carries a 1px border top+bottom.
# ``49 + 8 * 36 + 2 = 339`` matched the measured ``.ag-root-wrapper`` height
# exactly, which is what makes the derived height below reliable rather than a
# guess. Re-measure if the grid theme or ``GRID_ROW_HEIGHT`` changes.
_GRID_HEADER_HEIGHT = 49
_GRID_BORDER_HEIGHT = 2


def data_grid(
    column_defs: list[dict],
    row_data: list[dict],
    *,
    compact: bool = False,
    auto_height: bool = False,
    row_click_to: Callable[[dict], str] | None = None,
    on_cell_click: Callable[[Any], Any] | None = None,
    on_row_click: Callable[[Any], Awaitable[None]] | Callable[[Any], Any] | None = None,
    default_col_def: dict | None = None,
    selection: str = "single",
) -> ui.aggrid:
    """Render an AG Grid with the admin theme class + shared defaults.

    Height:
    - default → viewport-sized (``--admin-grid-height``); ``compact=True`` →
      the shorter ``--admin-grid-height-compact``. Both are *fixed*, so a grid
      holding fewer rows than the container leaves empty space below the last
      row.
    - ``auto_height=True`` → the height is *derived from the row count* and set
      inline, so there is no empty space under the last row. Use only when the
      caller bounds the row count; every row is laid out, so an unbounded grid
      gets an arbitrarily tall page. ``compact`` is ignored when
      ``auto_height`` is set.

      This deliberately does **not** use AG Grid's ``domLayout: "autoHeight"``.
      That was tried first and does not work in the NiceGUI embed: AG Grid grows
      its inner ``.ag-root-wrapper`` (measured 339px for 8 rows) while the outer
      NiceGUI element keeps the height Quasar computed for it (256px), so the
      grid paints 83px over whatever follows it — on the dashboard the Quick
      Actions section was overlapped and its heading hidden. Deriving a fixed
      height keeps the mechanism that already works and only changes where the
      number comes from.

    Click handling (all optional, async-safe):
    - ``row_click_to``: row dict → route; navigates on cellClicked (the common
      list→detail case).
    - ``on_cell_click`` / ``on_row_click``: raw handlers (sync or async) for the
      cellClicked / rowClicked events (e.g. opening a detail dialog).
    """
    col_def = {**_SHARED_DEFAULT_COL_DEF, **(default_col_def or {})}
    options: dict[str, Any] = {
        "columnDefs": column_defs,
        "rowData": row_data,
        "rowSelection": {"mode": "singleRow"} if selection == "single" else selection,
        "rowHeight": AdminMetrics.GRID_ROW_HEIGHT,
        "defaultColDef": col_def,
    }
    if auto_height:
        height_class = AdminClasses.GRID_AUTO
    else:
        height_class = AdminClasses.GRID_COMPACT if compact else AdminClasses.GRID
    grid = ui.aggrid(options).classes(f"w-full {height_class}")
    if auto_height:
        # At least one row's worth so a zero-row grid is not 0px tall.
        visible_rows = max(len(row_data), 1)
        grid.style(
            f"height: {_GRID_HEADER_HEIGHT + visible_rows * AdminMetrics.GRID_ROW_HEIGHT + _GRID_BORDER_HEIGHT}px"
        )

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
