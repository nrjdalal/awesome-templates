"""Admin design-system component library (#193 follow-up).

The single place that turns design tokens (``theme.py``) into NiceGUI elements.
Pages compose these builders instead of hand-writing ``ui.*`` + class strings,
so every admin surface shares one look and new pages stay consistent.

Import surface::

    from src._core.infrastructure.admin import components as c
    c.page_header("Users", subtitle="Manage accounts")
    with c.card():
        ...

Layering: theme.py (tokens) → components (builders) → base_admin_page + pages.
Components must NEVER import base_admin_page (cycle).
"""

from __future__ import annotations

from src._core.infrastructure.admin.components.charts import bar_chart
from src._core.infrastructure.admin.components.containers import (
    card,
    field_row,
    section,
    stat_card,
)
from src._core.infrastructure.admin.components.data import data_grid, pagination
from src._core.infrastructure.admin.components.dialogs import (
    action_dialog,
    confirm_dialog,
)
from src._core.infrastructure.admin.components.feedback import (
    empty_state,
    report_error,
    toast_error,
    toast_success,
    toast_warning,
)
from src._core.infrastructure.admin.components.forms import (
    number_field,
    select_field,
    text_field,
    textarea_field,
)
from src._core.infrastructure.admin.components.headers import page_header

__all__ = [
    "action_dialog",
    "bar_chart",
    "card",
    "confirm_dialog",
    "data_grid",
    "empty_state",
    "field_row",
    "number_field",
    "page_header",
    "pagination",
    "report_error",
    "section",
    "select_field",
    "stat_card",
    "text_field",
    "textarea_field",
    "toast_error",
    "toast_success",
    "toast_warning",
]
