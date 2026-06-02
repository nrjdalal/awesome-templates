"""Smoke + contract tests for the admin design-system components (#193 follow-up).

Gated on the ``admin`` extra via ``importorskip`` (matches the other admin
render tests). NiceGUI auto-creates an index client, so builders can be
instantiated here; we assert on element type, ``_classes`` and ``_props``
membership — never on rendered HTML.
"""

from __future__ import annotations

import pytest

pytest.importorskip("nicegui")

from nicegui import ui  # noqa: E402

from src._core.infrastructure.admin import components as c  # noqa: E402
from src._core.infrastructure.admin.theme import (  # noqa: E402
    AdminClasses,
    AdminMetrics,
)


@pytest.fixture(autouse=True)
def _ui_slot():
    """Provide a NiceGUI slot so builders can create elements regardless of
    suite ordering (other tests can leave the global slot stack empty)."""
    from nicegui.client import Client
    from nicegui.page import page as Page

    with Client(Page("/_components_test")):
        yield


# ── Forms: outlined enforced everywhere ──


def test_text_field_is_outlined():
    el = c.text_field("Username")
    assert isinstance(el, ui.input)
    assert el._props.get("outlined") is True
    assert el._props.get("dense") is True


def test_password_text_field_uses_password_type():
    assert c.text_field("Password", password=True)._props.get("type") == "password"
    assert c.text_field("User")._props.get("type") == "text"


def test_all_form_fields_are_outlined():
    assert c.textarea_field("Q")._props.get("outlined") is True
    assert c.number_field("n")._props.get("outlined") is True
    assert c.select_field("S", {"a": "a"})._props.get("outlined") is True


def test_clearable_and_chips_flags():
    assert c.text_field("x", clearable=True)._props.get("clearable") is True
    assert (
        c.select_field("S", {"a": "a"}, use_chips=True)._props.get("use-chips") is True
    )


# ── Data grid: theme class + shared options ──


def test_data_grid_carries_theme_and_defaults():
    grid = c.data_grid([{"field": "id"}], [{"id": 1}])
    assert isinstance(grid, ui.aggrid)
    assert AdminClasses.GRID in grid._classes
    options = grid._props["options"]
    assert options["rowHeight"] == AdminMetrics.GRID_ROW_HEIGHT
    assert options["defaultColDef"]["sortable"] is True
    assert options["defaultColDef"]["filter"] is True


def test_data_grid_compact_uses_compact_class():
    grid = c.data_grid([], [], compact=True)
    assert AdminClasses.GRID_COMPACT in grid._classes


def test_data_grid_merges_default_col_def():
    grid = c.data_grid([], [], default_col_def={"sortable": False, "flex": 1})
    default = grid._props["options"]["defaultColDef"]
    assert default["sortable"] is False  # override wins
    assert default["flex"] == 1
    assert default["resizable"] is True  # shared base preserved


# ── Leaf builders return the right element type ──


def test_leaf_builders_return_elements():
    assert isinstance(c.page_header("T", subtitle="s", back_to="/admin/"), ui.row)
    assert isinstance(c.stat_card("Calls", 42, icon="bolt"), ui.card)
    assert isinstance(c.field_row("Email", "a@b.com"), ui.row)
    assert isinstance(
        c.pagination(
            current=1, total_pages=3, on_prev=lambda: None, on_next=lambda: None
        ),
        ui.row,
    )


# ── Context-manager builders nest children ──


def test_context_manager_builders():
    with c.card() as card_el:
        assert isinstance(card_el, ui.card)
    with c.section("Title") as col:
        assert isinstance(col, ui.column)
    with c.empty_state() as col:
        assert isinstance(col, ui.column)


# Note: confirm_dialog's click→close→refresh ordering (close + on_success only on
# success, stay-open on failure) is exercised manually in the accounts migration;
# it can't be clicked in a headless test, and building UI inside an async task
# trips NiceGUI's slot-stack guard.
