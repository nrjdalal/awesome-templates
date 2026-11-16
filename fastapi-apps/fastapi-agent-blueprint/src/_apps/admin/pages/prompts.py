"""Prompt store page (#451, ADR 066).

One card per code-registered prompt. The card makes the three states an
operator has to reason about visible at once:

- the **code default** — what ships, and what agents serve when nothing is
  active or the store fails;
- the **active version** — what agents serve right now;
- the **version history** — every saved text, never edited in place.

Saving and activating are separate actions: "Save as new version" changes
nothing agents serve. "Activate" (also how a rollback is done) and "Revert to
code default" take effect on each process's next agent call — there is no cache.

Persona text is rendered with ``ui.label`` (escaped plain text) and edited in a
textarea, never through ``ui.html`` / ``ui.markdown``: it is operator input.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from nicegui import ui

from src._core.exceptions.base_exception import BaseCustomException
from src._core.infrastructure.admin import components as c
from src._core.infrastructure.admin.audit import AdminAction, AuditResult
from src._core.infrastructure.admin.audit.logger import get_audit_logger
from src._core.infrastructure.admin.auth import require_auth
from src._core.infrastructure.admin.base_admin_page import BaseAdminPage
from src._core.infrastructure.admin.error_handler import (
    AdminErrorHandler,
    admin_error_boundary,
)
from src._core.infrastructure.admin.layout import admin_layout, button_loading
from src._core.infrastructure.prompt.registry import (
    MAX_PROMPT_LENGTH,
    registered_prompts,
)
from src._core.infrastructure.prompt.service import PromptStoreService

_PAGE_KEY = "prompts"

# Set by ``src/_apps/admin/bootstrap.py``. The service is resolved per request
# so ``override_database`` (tests) is honoured, like every other admin page.
page_configs: list[BaseAdminPage] = []
service_provider: Callable[[], PromptStoreService] | None = None

_PRE_WRAP = "whitespace-pre-wrap text-body2"


def _service() -> PromptStoreService:
    if service_provider is None:
        raise RuntimeError("prompts page used before admin bootstrap wired it")
    return service_provider()


@ui.page("/admin/prompts")
@admin_error_boundary(context="prompts")
async def prompts_page() -> None:
    session = await require_auth(page_key=_PAGE_KEY)
    if session is None:
        return

    admin_layout(page_configs, current_domain="prompts", session=session)
    c.page_header(
        "Prompts",
        subtitle=(
            "Agent personas. The prompt-injection rules that agents append "
            "after the persona are fixed in code and not editable here."
        ),
    )

    prompts = registered_prompts()
    if not prompts:
        with c.empty_state("edit_note"):
            ui.label("No agent has registered an editable prompt.")
        return

    for name in sorted(prompts):
        await _prompt_card(name, prompts[name])


async def _prompt_card(name: str, code_default: str) -> None:
    holder = ui.column().classes("w-full q-mb-lg")

    async def render() -> None:
        holder.clear()
        service = _service()
        active = await service.get_active(name)
        versions = await service.list_versions(name)
        # Captured at render time and sent with every write: if a colleague
        # activated or reverted since, the write is refused (optimistic check).
        expected_active = active.version if active else None

        with holder, c.card(classes="w-full"):
            with ui.row().classes("w-full items-center justify-between"):
                ui.label(name).classes("text-h6")
                if active:
                    ui.badge(f"Active: v{active.version}").props("color=primary")
                else:
                    ui.badge("Serving code default").props("color=grey-7")

            # gap: 0 — NiceGUI's row gap stacks on top of the Quasar gutter and
            # wraps a 6/6 split (admin-design-system.md, multi-column trap).
            with ui.row().classes("w-full q-col-gutter-md").style("gap: 0"):
                with ui.column().classes("col-12 col-md-6"):
                    ui.label("Code default").classes("text-subtitle2")
                    ui.label(code_default).classes(_PRE_WRAP)
                with ui.column().classes("col-12 col-md-6"):
                    if active:
                        ui.label(
                            f"Active version v{active.version} · {active.activated_by}"
                        ).classes("text-subtitle2")
                        ui.label(active.content).classes(_PRE_WRAP)
                    else:
                        ui.label("Active version").classes("text-subtitle2")
                        ui.label(
                            "None — agents serve the code default. A change to "
                            "the code default takes effect only while no "
                            "version is active."
                        ).classes("text-caption")

            ui.separator().classes("q-my-sm")
            editor = c.textarea_field(
                "New version",
                value=active.content if active else code_default,
            ).classes("w-full")
            editor.props(f"counter maxlength={MAX_PROMPT_LENGTH}")

            with ui.row().classes("q-gutter-sm items-center"):
                save_btn = ui.button("Save as new version").props("color=primary")
                save_btn.on_click(
                    lambda: _save(name, editor.value or "", save_btn, render)
                )
                ui.label("Saving does not change what agents serve.").classes(
                    "text-caption"
                )
                if active:
                    revert_btn = ui.button("Revert to code default").props("flat")
                    revert_btn.on_click(
                        lambda: _revert(name, expected_active, revert_btn, render)
                    )

            if versions:
                ui.label("Versions").classes("text-subtitle2 q-mt-md")
                for v in versions:
                    with ui.row().classes("w-full items-start q-gutter-sm no-wrap"):
                        ui.label(f"v{v.version}").classes("text-weight-bold")
                        created = (
                            v.created_at.isoformat(sep=" ", timespec="minutes")
                            if v.created_at
                            else ""
                        )
                        ui.label(f"{v.created_by} · {created}").classes("text-caption")
                        ui.label(_preview(v.content)).classes(
                            "col text-caption ellipsis"
                        )
                        if active and active.version == v.version:
                            ui.badge("active").props("color=primary outline")
                        else:
                            btn = ui.button("Activate").props("flat dense")
                            # NiceGUI passes the click event to a handler that
                            # takes parameters, so it needs its own slot ahead of
                            # the bound defaults.
                            btn.on_click(
                                lambda _event, ver=v.version, b=btn: _activate(
                                    name, ver, expected_active, b, render
                                )
                            )

    await render()


def _preview(text: str, limit: int = 120) -> str:
    flat = " ".join(text.split())
    return flat if len(flat) <= limit else flat[: limit - 1] + "…"


async def _authorised_username() -> str | None:
    """Re-check the permission at write time, not only at page load.

    A page can stay open after the operator's permission was revoked; the
    write must still be refused.
    """
    session = await require_auth(page_key=_PAGE_KEY)
    return session.username if session else None


async def _run_write(
    *,
    action: AdminAction,
    name: str,
    button: Any,
    write: Callable[[str], Any],
    record_id: Callable[[Any], str],
    success: str,
    rerender: Callable[[], Any],
) -> None:
    username = await _authorised_username()
    if username is None:
        # Refused before any side effect, but still evidence: a write attempted
        # after the permission was revoked (or a replayed event) is exactly what
        # an investigation looks for.
        await get_audit_logger().log(
            action=action,
            domain=_PAGE_KEY,
            record_id=name,
            result=AuditResult.FAILURE,
            failure_reason="PERMISSION_DENIED",
        )
        return
    async with button_loading(button):
        try:
            result = await write(username)
        except BaseCustomException as exc:
            await get_audit_logger().log(
                action=action,
                domain=_PAGE_KEY,
                record_id=name,
                result=AuditResult.FAILURE,
                failure_reason=exc.error_code,
            )
            ui.notify(exc.message, type="warning")
            return
        except Exception as exc:  # noqa: BLE001 - delegated to handler
            await get_audit_logger().log(
                action=action,
                domain=_PAGE_KEY,
                record_id=name,
                result=AuditResult.FAILURE,
                failure_reason=type(exc).__name__,
            )
            await AdminErrorHandler.handle(
                exc, context=f"prompts_{action.value.lower()}"
            )
            return
    await get_audit_logger().log(
        action=action,
        domain=_PAGE_KEY,
        record_id=record_id(result),
        result=AuditResult.SUCCESS,
    )
    ui.notify(success, type="positive")
    await rerender()


async def _save(name: str, content: str, button: Any, rerender) -> None:
    await _run_write(
        action=AdminAction.PROMPT_VERSION_SAVE,
        name=name,
        button=button,
        write=lambda user: _service().save_version(name, content, user),
        record_id=lambda saved: f"{name}@{saved.version}",
        success="Saved as a new version. Activate it to put it live.",
        rerender=rerender,
    )


async def _activate(
    name: str, version: int, expected_active: int | None, button: Any, rerender
) -> None:
    await _run_write(
        action=AdminAction.PROMPT_ACTIVATE,
        name=name,
        button=button,
        write=lambda user: _service().activate(
            name, version, user, expected_active=expected_active
        ),
        record_id=lambda _: f"{name}@{version}",
        success=f"v{version} is now live for {name}.",
        rerender=rerender,
    )


async def _revert(
    name: str, expected_active: int | None, button: Any, rerender
) -> None:
    await _run_write(
        action=AdminAction.PROMPT_REVERT,
        name=name,
        button=button,
        write=lambda user: _service().revert_to_code_default(
            name, expected_active=expected_active
        ),
        record_id=lambda _: name,
        success=f"{name} now serves the code default.",
        rerender=rerender,
    )
