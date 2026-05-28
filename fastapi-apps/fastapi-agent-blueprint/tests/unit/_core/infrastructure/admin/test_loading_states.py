"""Unit tests for admin loading states (#198): button_loading + skeleton counts."""

from __future__ import annotations

import pytest

from src._core.infrastructure.admin.base_admin_page import BaseAdminPage, ColumnConfig
from src._core.infrastructure.admin.layout import button_loading


class _FakeButton:
    """Records props() calls the way NiceGUI's ui.button exposes them."""

    def __init__(self) -> None:
        self.calls: list[tuple[str | None, str | None]] = []

    def props(self, add: str | None = None, *, remove: str | None = None):
        self.calls.append((add, remove))
        return self


@pytest.mark.asyncio
async def test_button_loading_sets_then_clears_on_success():
    btn = _FakeButton()
    async with button_loading(btn):
        assert btn.calls == [("loading disable", None)]
    assert btn.calls[-1] == (None, "loading disable")


@pytest.mark.asyncio
async def test_button_loading_clears_on_exception():
    btn = _FakeButton()
    with pytest.raises(ValueError):
        async with button_loading(btn):
            raise ValueError("boom")
    # loading was set, then removed in finally despite the exception
    assert btn.calls[0] == ("loading disable", None)
    assert btn.calls[-1] == (None, "loading disable")


@pytest.mark.asyncio
async def test_button_loading_clears_on_early_return():
    btn = _FakeButton()

    async def handler() -> None:
        async with button_loading(btn):
            return  # early return inside the context

    await handler()
    assert btn.calls[-1] == (None, "loading disable")


def test_list_skeleton_rows_defaults_to_8():
    page = BaseAdminPage(domain_name="t", display_name="T", icon="x")
    assert page.page_size == 20
    assert page._list_skeleton_rows() == 8


def test_list_skeleton_rows_match_small_page_size():
    page = BaseAdminPage(domain_name="t", display_name="T", icon="x", page_size=3)
    assert page._list_skeleton_rows() == 3


def test_detail_skeleton_rows_minimum_4():
    page = BaseAdminPage(
        domain_name="t",
        display_name="T",
        icon="x",
        columns=[ColumnConfig(field_name="id", header_name="ID")],
    )
    assert page._detail_skeleton_rows() == 4


def test_detail_skeleton_rows_mirror_visible_columns():
    columns = [ColumnConfig(field_name=f"f{i}", header_name=f"F{i}") for i in range(6)]
    columns.append(ColumnConfig(field_name="secret", header_name="S", hidden=True))
    page = BaseAdminPage(domain_name="t", display_name="T", icon="x", columns=columns)
    # 6 visible (hidden excluded) → max(6, 4) == 6
    assert page._detail_skeleton_rows() == 6
