from nicegui import ui

from src._core.infrastructure.admin.auth import (
    AdminAuthProvider,
    get_admin_auth_provider,
)
from src.auth.domain.exceptions.auth_exceptions import InvalidCredentialsException


@ui.page("/admin/login")
def login_page():
    with ui.card().classes("absolute-center w-80"):
        ui.label("Admin Login").classes("text-h5 q-mb-md")
        username = ui.input("Username").classes("full-width")
        password = ui.input(
            "Password", password=True, password_toggle_button=True
        ).classes("full-width")

        async def try_login():
            try:
                session = await get_admin_auth_provider().authenticate(
                    username.value,
                    password.value,
                )
            except InvalidCredentialsException:
                ui.notify("Invalid credentials", type="negative")
            else:
                AdminAuthProvider.login(session)
                ui.navigate.to("/admin/")

        password.on("keydown.enter", try_login)
        ui.button("Login", on_click=try_login).classes("q-mt-md full-width")
