"""Dedicated admin error page for critical failures (#195).

Intentionally has NO auth gate: a critical failure may itself be a DB/auth
outage, and the auth gate (``require_auth*``) hits the DB — gating here would
loop. This page therefore does not call ``admin_layout``, touches no DB, and
mutates no session state. It shows only a generic message plus a validated
correlation id so the operator can quote it to support.

Listed in ``tests/unit/_core/infrastructure/admin/test_route_coverage.py``
``_EXEMPT_ROUTES`` with this justification.
"""

import re

from nicegui import ui

from src._core.infrastructure.admin.theme import AdminClasses

# Correlation ids are short hex/uuid-ish tokens; reject anything else before
# echoing the query value back into the page (no reflected-content surprises).
_RID_PATTERN = re.compile(r"^[A-Za-z0-9-]{1,64}$")


@ui.page("/admin/error")
def error_page(rid: str = "") -> None:
    with ui.card().classes("absolute-center w-96 items-center"):
        ui.icon("error_outline").classes("text-h2 text-negative")
        ui.label("Something went wrong").classes("text-h5 q-mb-sm")
        ui.label(
            "An unexpected error occurred. Please contact your administrator."
        ).classes("text-body2 text-center q-mb-md")
        if rid and _RID_PATTERN.match(rid):
            ui.label(f"Reference ID: {rid}").classes(
                f"text-caption {AdminClasses.MUTED} q-mb-md"
            )
        ui.button(
            "Return to dashboard",
            on_click=lambda: ui.navigate.to("/admin/"),
        ).props("color=primary")
