from nicegui import ui

from src._core.infrastructure.admin.auth import require_auth
from src._core.infrastructure.admin.base_admin_page import BaseAdminPage
from src._core.infrastructure.admin.error_handler import admin_error_boundary
from src._core.infrastructure.admin.layout import admin_layout
from src.user.interface.admin.configs.user_admin_config import user_admin_page

# page_configs is injected by bootstrap_admin() after discovery
page_configs: list[BaseAdminPage] = []


@ui.page("/admin/user")
@admin_error_boundary(context="user_list")
async def user_list_page(page: int = 1, search: str = ""):
    session = await require_auth(page_key="user")
    if session is None:
        return
    admin_layout(page_configs, current_domain="user", session=session)
    await user_admin_page.render_list(page=page, search=search)


@ui.page("/admin/user/{record_id}")
@admin_error_boundary(context="user_detail")
async def user_detail_page(record_id: int):
    session = await require_auth(page_key="user")
    if session is None:
        return
    admin_layout(page_configs, current_domain="user", session=session)
    await user_admin_page.render_detail(record_id=record_id)
