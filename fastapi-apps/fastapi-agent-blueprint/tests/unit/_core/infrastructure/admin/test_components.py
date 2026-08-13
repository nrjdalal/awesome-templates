"""Smoke + contract tests for the admin design-system components (#193 follow-up).

Gated on the ``admin`` extra via ``importorskip`` (matches the other admin
render tests). NiceGUI auto-creates an index client, so builders can be
instantiated here; we assert on element type, ``_classes`` and ``_props``
membership — never on rendered HTML.
"""

from __future__ import annotations

from typing import Any

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
    assert "height" not in (grid._style or {})


def test_data_grid_auto_height_derives_height_from_row_count():
    """Height scales with rows so no empty space sits under the last row.

    Asserts the derived value, not just that *some* height was set: the point of
    the feature is the number. `49 + rows * 36 + 2` was measured against the
    real `.ag-root-wrapper` in the NiceGUI embed.
    """
    rows = [{"id": i} for i in range(8)]
    grid = c.data_grid([{"field": "id"}], rows, auto_height=True)
    assert AdminClasses.GRID_AUTO in grid._classes
    assert AdminClasses.GRID not in grid._classes
    assert AdminClasses.GRID_COMPACT not in grid._classes
    assert grid._style["height"] == f"{49 + 8 * AdminMetrics.GRID_ROW_HEIGHT + 2}px"

    # Three rows must be shorter than eight — the whole point.
    shorter = c.data_grid([{"field": "id"}], rows[:3], auto_height=True)
    assert shorter._style["height"] == f"{49 + 3 * AdminMetrics.GRID_ROW_HEIGHT + 2}px"


def test_data_grid_auto_height_never_collapses_to_zero():
    """A zero-row grid still reserves one row, so it cannot render 0px tall."""
    grid = c.data_grid([{"field": "id"}], [], auto_height=True)
    assert grid._style["height"] == f"{49 + 1 * AdminMetrics.GRID_ROW_HEIGHT + 2}px"


def test_data_grid_does_not_use_ag_grid_dom_layout_auto_height():
    """`domLayout: autoHeight` is broken in the NiceGUI embed — never emit it.

    AG Grid grows its inner `.ag-root-wrapper` (measured 339px for 8 rows) while
    the outer NiceGUI element keeps Quasar's computed height (256px), so the grid
    paints over the following section. Reaching for the option again is the
    natural instinct; this test is the tripwire.
    """
    variants: tuple[dict[str, Any], ...] = (
        {},
        {"compact": True},
        {"auto_height": True},
    )
    for kwargs in variants:
        grid = c.data_grid([], [], **kwargs)
        assert "domLayout" not in grid._props["options"]


def test_data_grid_auto_height_overrides_compact():
    """`compact` imposes a height, so it cannot coexist with autoHeight."""
    grid = c.data_grid([], [], compact=True, auto_height=True)
    assert AdminClasses.GRID_AUTO in grid._classes
    assert AdminClasses.GRID_COMPACT not in grid._classes


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
