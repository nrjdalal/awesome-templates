"""Feedback builders for the admin design system (#193 follow-up).

``toast_*`` standardize ``ui.notify`` types. ``report_error`` is the ONLY path
for surfacing a caught exception — it routes through ``AdminErrorHandler`` which
sanitizes (never leaks ``str(exc)`` to the UI). ``empty_state`` is the single
empty-list markup, shared with BaseAdminPage.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from nicegui import ui

from src._core.infrastructure.admin.theme import AdminClasses


def toast_success(message: str) -> None:
    ui.notify(message, type="positive")


def toast_warning(message: str) -> None:
    ui.notify(message, type="warning")


def toast_error(message: str) -> None:
    """Show a sanitized error toast. NEVER pass ``str(exc)`` — use report_error."""
    ui.notify(message, type="negative")


async def report_error(exc: Exception, *, context: str) -> None:
    """Route a caught exception through the sanitizing admin error handler."""
    from src._core.infrastructure.admin.error_handler import AdminErrorHandler

    await AdminErrorHandler.handle(exc, context=context)


@contextmanager
def empty_state(icon: str = "inbox") -> Iterator[ui.column]:
    """A centered, muted empty-state column. Caller adds the message label(s)."""
    with ui.column().classes(f"w-full {AdminClasses.EMPTY_STATE}") as column:
        ui.icon(icon).classes("text-h2")
        yield column
