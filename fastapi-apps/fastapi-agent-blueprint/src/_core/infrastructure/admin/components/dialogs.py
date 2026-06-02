"""Dialog builders for the admin design system (#193 follow-up).

``action_dialog`` is a context manager for arbitrary dialog bodies.
``confirm_dialog`` is an async coroutine for the common confirm-an-action flow;
it owns ONLY the loading + close/ordering — ``on_confirm`` owns its own
try/except + audit + notify and returns ``success`` so the dialog stays open on
failure and closes (then refreshes) only on success.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterator
from contextlib import contextmanager

from nicegui import ui

from src._core.infrastructure.admin.layout import button_loading
from src._core.infrastructure.admin.theme import AdminClasses


@contextmanager
def action_dialog(
    title: str,
    *,
    width: str = "480px",
    subtitle: str | None = None,
) -> Iterator[tuple[ui.dialog, ui.card]]:
    """Open a dialog with a title (and optional subtitle); yield (dialog, card).

    The caller fills the body inside the ``with`` and adds its own footer
    buttons (e.g. Save/Cancel). The dialog is opened on exit.
    """
    with (
        ui.dialog() as dialog,
        ui.card().style(f"width: {width}; max-width: 95vw") as card,
    ):
        ui.label(title).classes("text-h6")
        if subtitle:
            ui.label(subtitle).classes(f"text-caption {AdminClasses.MUTED} q-mb-sm")
        yield dialog, card
    dialog.open()


async def confirm_dialog(
    title: str,
    message: str,
    *,
    on_confirm: Callable[[], Awaitable[bool]],
    on_success: Callable[[], Awaitable[None]] | None = None,
    confirm_label: str = "Confirm",
    cancel_label: str = "Cancel",
    danger: bool = False,
    width: str = "420px",
) -> None:
    """Build + open a confirm dialog.

    Contract:
    - ``on_confirm()`` performs the work and returns ``True`` on success. It owns
      its own try/except, audit logging and user notifications.
    - The builder wraps it in ``button_loading`` and, **only when it returns
      True**, closes the dialog and (if given) awaits ``on_success`` (e.g. a list
      refresh) AFTER the close. On ``False`` the dialog stays open.
    """
    with ui.dialog() as dialog, ui.card().style(f"width: {width}; max-width: 95vw"):
        ui.label(title).classes("text-h6")
        if message:
            classes = "text-caption q-mb-md" + (" text-negative" if danger else "")
            ui.label(message).classes(classes)

        async def _confirm() -> None:
            async with button_loading(confirm_btn):
                ok = await on_confirm()
            # Close + refresh OUTSIDE the loading context (button not yet torn
            # down during the await); only on success.
            if ok:
                dialog.close()
                if on_success is not None:
                    await on_success()

        with ui.row().classes("q-mt-md justify-end q-gutter-sm"):
            ui.button(cancel_label, on_click=dialog.close).props("flat")
            confirm_btn = ui.button(confirm_label, on_click=_confirm).props(
                "color=negative" if danger else "color=primary"
            )
    dialog.open()
