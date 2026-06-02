"""Container + content builders for the admin design system (#193 follow-up).

``card`` / ``section`` are context managers (they hold children); ``stat_card``
and ``field_row`` are leaf builders that return the element.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from nicegui import ui

from src._core.infrastructure.admin.theme import AdminClasses


@contextmanager
def card(*, clickable_to: str | None = None, classes: str = "") -> Iterator[ui.card]:
    """A themed card container. ``clickable_to`` makes the whole card navigate."""
    element = ui.card().classes(classes)
    if clickable_to is not None:
        element.classes("cursor-pointer").on(
            "click", lambda: ui.navigate.to(clickable_to)
        )
    with element:
        yield element


@contextmanager
def section(title: str | None = None, *, classes: str = "") -> Iterator[ui.column]:
    """A vertical content section with an optional heading."""
    with ui.column().classes(f"w-full q-gutter-sm {classes}".strip()) as column:
        if title:
            ui.label(title).classes("text-subtitle1 text-weight-bold")
        yield column


def stat_card(label: str, value: str | int, *, icon: str | None = None) -> ui.card:
    """A metric tile: caption label + large value (replaces ai_usage tiles)."""
    with ui.card().classes("q-pa-md") as element:
        if icon is not None:
            ui.icon(icon).classes("text-h5 text-primary")
        ui.label(str(label)).classes(f"text-caption {AdminClasses.MUTED}")
        ui.label(str(value)).classes("text-h6")
    return element


def field_row(label: str, value: str, *, is_empty: bool = False) -> ui.row:
    """One label/value detail row. ``value`` is pre-formatted by the caller."""
    with ui.row().classes("items-center q-py-xs") as row:
        ui.label(label).classes(AdminClasses.FIELD_LABEL)
        value_label = ui.label(value)
        if is_empty:
            value_label.classes(AdminClasses.EMPTY_VALUE)
    return row
