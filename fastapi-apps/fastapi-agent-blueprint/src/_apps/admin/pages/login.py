from fastapi import Request
from nicegui import app, ui

from src._core.infrastructure.admin.auth import (
    AdminAuthProvider,
    get_admin_auth_provider,
)
from src._core.infrastructure.admin.layout import button_loading
from src.auth.domain.exceptions.auth_exceptions import (
    AdminCredentialDisabledException,
    AdminSetupRequiredException,
    InvalidCredentialsException,
)


@ui.page("/admin/login")
def login_page(request: Request):
    # Capture client IP best-effort for the audit log (#196). Behind a trusted
    # proxy you would need to parse X-Forwarded-For instead; that requires
    # explicit proxy-trust configuration so we don't do it implicitly here.
    client_ip = request.client.host if request.client else None

    with ui.card().classes("absolute-center w-80"):
        ui.label("Admin Login").classes("text-h5 q-mb-md")
        username = ui.input("Username").classes("full-width")
        password = ui.input(
            "Password", password=True, password_toggle_button=True
        ).classes("full-width")

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
                except (InvalidCredentialsException, AdminCredentialDisabledException):
                    ui.notify("Invalid credentials", type="negative")
                else:
                    AdminAuthProvider.login(session)
                    target = "/admin/"
            # Navigate only after loading state is cleared (button not yet torn down).
            if target:
                ui.navigate.to(target)

        password.on("keydown.enter", try_login)
        login_btn = ui.button("Login", on_click=try_login).classes("q-mt-md full-width")
