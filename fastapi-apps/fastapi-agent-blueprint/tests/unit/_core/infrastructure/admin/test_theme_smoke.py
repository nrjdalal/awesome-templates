"""Smoke tests that exercise theme code paths needing nicegui (#193).

Gated on the ``admin`` extra via ``importorskip`` so they are skipped on a
minimal install, matching the per-domain admin config tests.
"""

from __future__ import annotations

import pytest

pytest.importorskip("nicegui")

from src._core.infrastructure.admin import theme  # noqa: E402
from src._core.infrastructure.admin.base_admin_page import (  # noqa: E402
    BaseAdminPage,
    ColumnConfig,
)
from src._core.infrastructure.admin.theme import AdminMetrics  # noqa: E402


def test_install_admin_theme_css_is_idempotent(monkeypatch: pytest.MonkeyPatch):
    """install_admin_theme_css injects once and no-ops on repeat calls."""
    calls: list[bool] = []

    def _fake_add_css(content: str, *, shared: bool = False) -> None:
        calls.append(shared)

    from nicegui import ui

    monkeypatch.setattr(ui, "add_css", _fake_add_css)
    # Reset the module-level guard so the test is order-independent.
    monkeypatch.setattr(theme, "_theme_css_installed", False)

    theme.install_admin_theme_css()
    theme.install_admin_theme_css()

    assert calls == [True], "CSS must be injected exactly once, with shared=True"


def test_build_column_defs_apply_min_width_and_flex():
    page = BaseAdminPage(
        domain_name="t",
        display_name="T",
        columns=[
            ColumnConfig(field_name="id", header_name="ID", width=80),
            ColumnConfig(field_name="name", header_name="Name"),
        ],
    )
    defs = {d["field"]: d for d in page.build_column_defs()}

    # Explicit width is honored exactly; no flex / minWidth floor applied.
    assert defs["id"]["width"] == 80
    assert "flex" not in defs["id"]
    assert "minWidth" not in defs["id"]
    # Width-less column flexes to fill, with a sane minimum.
    assert defs["name"]["flex"] == 1
    assert defs["name"]["minWidth"] == AdminMetrics.GRID_MIN_COL_WIDTH
