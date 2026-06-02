"""Page-header builder for the admin design system (#193 follow-up).

One builder covers every observed header variant: title-only, title+subtitle,
back-button+title, and title+actions. Pages compose this instead of hand-writing
``ui.label(...).classes("text-h5 q-mb-md")``.
"""

from __future__ import annotations

from collections.abc import Callable

from nicegui import ui

from src._core.infrastructure.admin.theme import AdminClasses


def page_header(
    title: str,
    *,
    subtitle: str | None = None,
    back_to: str | None = None,
    actions: Callable[[], None] | None = None,
) -> ui.row:
    """Render a page header. Returns the header row.

    - ``back_to``: route → renders a leading back button that navigates there.
    - ``subtitle``: muted sub-label under the title.
    - ``actions``: slot builder rendered right-aligned (e.g. a "New" button).
    """
    with ui.row().classes("items-center justify-between w-full q-mb-md") as header:
        with ui.row().classes("items-center q-gutter-sm"):
            if back_to is not None:
                ui.button(
                    icon="arrow_back",
                    on_click=lambda: ui.navigate.to(back_to),
                ).props("flat round")
            with ui.column().classes("q-gutter-none"):
                ui.label(title).classes("text-h5")
                if subtitle:
                    ui.label(subtitle).classes(f"text-caption {AdminClasses.MUTED}")
        if actions is not None:
            with ui.row().classes("items-center q-gutter-sm"):
                actions()
    return header
