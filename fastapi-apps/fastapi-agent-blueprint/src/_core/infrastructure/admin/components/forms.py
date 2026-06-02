"""Form-field builders for the admin design system (#193 follow-up).

All builders force ``outlined`` chrome so inputs are consistent everywhere —
fixing the prior drift where login used ``outlined`` but accounts / setup /
change_password did not. Leaf builders: return the element for chaining
``.classes("full-width")`` / ``.on(...)``.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from nicegui import ui


def text_field(
    label: str,
    *,
    value: str = "",
    password: bool = False,
    clearable: bool = False,
    placeholder: str | None = None,
    on_change: Callable[..., Any] | None = None,
) -> ui.input:
    """An outlined text/password input."""
    element = ui.input(
        label,
        value=value,
        placeholder=placeholder,
        password=password,
        password_toggle_button=password,
        on_change=on_change,
    )
    props = "outlined dense"
    if clearable:
        props += " clearable"
    return element.props(props)


def textarea_field(
    label: str,
    *,
    value: str = "",
    placeholder: str | None = None,
    autogrow: bool = True,
) -> ui.textarea:
    """An outlined (optionally autogrowing) textarea."""
    element = ui.textarea(label, value=value, placeholder=placeholder)
    props = "outlined"
    if autogrow:
        props += " autogrow"
    return element.props(props)


def number_field(
    label: str,
    *,
    value: float | None = None,
    min: float | None = None,  # noqa: A002 - mirrors ui.number kwarg name
    max: float | None = None,  # noqa: A002 - mirrors ui.number kwarg name
    step: float = 1,
) -> ui.number:
    """An outlined numeric input."""
    return ui.number(label, value=value, min=min, max=max, step=step).props(
        "outlined dense"
    )


def select_field(
    label: str,
    options: Any,
    *,
    value: Any = None,
    multiple: bool = False,
    use_chips: bool = False,
    on_change: Callable[..., Any] | None = None,
) -> ui.select:
    """An outlined select (single or multiple, optionally chip-rendered)."""
    element = ui.select(
        options,
        label=label,
        value=value,
        multiple=multiple,
        on_change=on_change,
    )
    props = "outlined dense"
    if use_chips:
        props += " use-chips"
    return element.props(props)
