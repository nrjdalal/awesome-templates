from fastapi import Request
from nicegui import app, ui

from src._core.config import settings
from src._core.infrastructure.admin.auth import (
    AdminAuthProvider,
    get_admin_auth_provider,
)
from src._core.infrastructure.admin.layout import button_loading
from src._core.infrastructure.admin.theme import AdminClasses
from src.admin_identity.domain.exceptions.admin_identity_exceptions import (
    AdminCredentialDisabledException,
    AdminInvalidCredentialsException,
    AdminSetupRequiredException,
)


@ui.page("/admin/login")
def login_page(request: Request):
    # Capture client IP best-effort for the audit log (#196). Behind a trusted
    # proxy you would need to parse X-Forwarded-For instead; that requires
    # explicit proxy-trust configuration so we don't do it implicitly here.
    client_ip = request.client.host if request.client else None

    # Distinct dark background for the auth screen (page-scoped).
    ui.query("body").classes(AdminClasses.LOGIN_BG)

    with ui.card().classes(
        f"absolute-center items-center q-pa-lg {AdminClasses.LOGIN_CARD}"
    ):
        ui.icon("smart_toy").classes("text-primary").style("font-size: 3rem")
        ui.label(settings.admin_brand_name).classes("text-h6 text-weight-bold q-mt-sm")
        ui.label("ADMIN").classes(f"{AdminClasses.MUTED} q-mb-md").style(
            "letter-spacing: 0.25em; font-size: 0.7rem"
        )
        username = ui.input("Username").props("outlined").classes("full-width")
        password = (
            ui.input("Password", password=True, password_toggle_button=True)
            .props("outlined")
            .classes("full-width q-mt-sm")
        )

        async def try_login():
            target: str | None = None
            async with button_loading(login_btn):
                try:
                    session = await get_admin_auth_provider().authenticate(
                        username.value,
                        password.value,
                        ip_address=client_ip,
                    )
                except AdminSetupRequiredException:
                    app.storage.user["setup_granted"] = True
                    target = "/admin/setup"
                except (
                    AdminInvalidCredentialsException,
                    AdminCredentialDisabledException,
                ):
                    ui.notify("Invalid credentials", type="negative")
                else:
                    AdminAuthProvider.login(session)
                    target = "/admin/"
            # Navigate only after loading state is cleared (button not yet torn down).
            if target:
                ui.navigate.to(target)

        password.on("keydown.enter", try_login)
        login_btn = (
            ui.button("Login", on_click=try_login)
            .props("color=primary unelevated size=lg")
            .classes("q-mt-md full-width")
        )
