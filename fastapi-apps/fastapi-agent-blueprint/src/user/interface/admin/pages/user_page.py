from nicegui import ui

from src._core.infrastructure.admin.auth import require_auth
from src._core.infrastructure.admin.base_admin_page import BaseAdminPage
from src._core.infrastructure.admin.layout import admin_layout
from src.user.interface.admin.configs.user_admin_config import user_admin_page

# page_configs is injected by bootstrap_admin() after discovery
page_configs: list[BaseAdminPage] = []


@ui.page("/admin/user")
async def user_list_page(page: int = 1, search: str = ""):
    if not await require_auth():
        return
    admin_layout(page_configs, current_domain="user")
    await user_admin_page.render_list(page=page, search=search)


@ui.page("/admin/user/{record_id}")
async def user_detail_page(record_id: int):
    if not await require_auth():
        return
    admin_layout(page_configs, current_domain="user")
    await user_admin_page.render_detail(record_id=record_id)
