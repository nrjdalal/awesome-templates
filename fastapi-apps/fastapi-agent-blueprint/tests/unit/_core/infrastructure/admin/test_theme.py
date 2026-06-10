"""Pure-constant tests for the admin theme module (#193).

These intentionally import nothing from nicegui — ``theme.py`` keeps its nicegui
import lazy inside ``install_admin_theme_css`` — so they run under
``make check-core`` even when the ``admin`` extra is not installed.

The admin shell uses a single Toss-style theme (no preset selection).
"""

from __future__ import annotations

from src._core.infrastructure.admin.theme import (
    EMPTY_DISPLAY,
    AdminClasses,
    AdminColors,
    AdminMetrics,
    AdminVars,
    build_admin_css,
)


def _public_values(cls: type) -> list:
    return [v for k, v in vars(cls).items() if not k.startswith("_")]


def test_empty_display_is_em_dash():
    assert EMPTY_DISPLAY == "—"


def test_brand_colors_are_hex():
    values = _public_values(AdminColors)
    assert values, "AdminColors must define at least one color"
    assert all(isinstance(v, str) and v.startswith("#") for v in values)


def test_primary_is_tds_blue():
    """Single-theme brand primary (also the chart bar fill) is the TDS blue."""
    assert AdminColors.PRIMARY == "#3182f6"


def test_css_var_names_are_custom_properties():
    values = _public_values(AdminVars)
    assert values
    assert all(isinstance(v, str) and v.startswith("--") for v in values)


def test_helper_class_names_are_admin_prefixed():
    values = _public_values(AdminClasses)
    assert values
    assert all(isinstance(v, str) and v.startswith("admin-") for v in values)


def test_metrics_are_numeric():
    values = _public_values(AdminMetrics)
    assert values
    assert all(isinstance(v, int) for v in values)


def test_css_defines_light_and_dark_blocks():
    css = build_admin_css()
    assert ":root {" in css
    assert ".body--dark {" in css


def test_css_defines_every_token_in_both_themes():
    """Brand/shape live in :root; content + chrome surfaces flip into dark."""
    css = build_admin_css()
    root_block = css.split(".body--dark")[0]
    dark_block = css[css.index(".body--dark") :]

    # Brand is :root-only (constant across light/dark).
    for var in (AdminVars.Q_PRIMARY, AdminVars.Q_NEGATIVE, AdminVars.RADIUS):
        assert var in root_block, f"{var} missing from :root"

    # Content + chrome surfaces are defined in BOTH blocks so they flip.
    for var in (
        AdminVars.SURFACE,
        AdminVars.BORDER,
        AdminVars.TEXT_MUTED,
        AdminVars.ROW_ALT,
        AdminVars.HEADER_BG,
        AdminVars.DRAWER_TEXT,
        AdminVars.CHROME_BORDER,
    ):
        assert var in root_block, f"{var} missing from :root"
        assert var in dark_block, f"{var} missing from .body--dark"


def test_chrome_flips_light_to_dark():
    """Toss chrome is white in light mode and dark in dark mode (not constant)."""
    css = build_admin_css()
    root_block = css.split(".body--dark")[0]
    dark_block = css[css.index(".body--dark") :]
    assert f"{AdminVars.HEADER_BG}: #ffffff" in root_block  # light = white sidebar
    assert f"{AdminVars.HEADER_BG}: #191f28" in dark_block  # dark = TDS grey 900


def test_css_defines_helper_class_selectors():
    css = build_admin_css()
    for cls in (
        AdminClasses.HEADER,
        AdminClasses.DRAWER,
        AdminClasses.NAV_ACTIVE,
        AdminClasses.ACCENT_ICON,
        AdminClasses.FIELD_LABEL,
        AdminClasses.MUTED,
        AdminClasses.SUCCESS_SURFACE,
        AdminClasses.GRID,
        AdminClasses.GRID_COMPACT,
        AdminClasses.PAGINATION,
        AdminClasses.EMPTY_STATE,
        AdminClasses.PRE,
        AdminClasses.HIDDEN,
    ):
        assert f".{cls}" in css, f"selector .{cls} missing from CSS"


def test_css_styles_alternating_grid_rows_via_theming_vars():
    """NiceGUI 3.x quartz theme reads --ag-* custom properties, not .ag-row-odd."""
    css = build_admin_css()
    assert "--ag-odd-row-background-color" in css
    assert "--ag-row-hover-color" in css


def test_css_forces_grid_cells_visible():
    """AG Grid v33 can leave rows stuck `visibility:hidden` via `ag-delay-render`;
    the theme forces admin grid cells visible (#234)."""
    css = build_admin_css()
    assert ".admin-grid .ag-cell" in css
    assert "visibility: visible" in css


def test_css_defines_style_tokens_and_component_overrides():
    """The theme drives shape/elevation tokens + Quasar component overrides."""
    css = build_admin_css()
    for var in (
        AdminVars.RADIUS,
        AdminVars.RADIUS_BUTTON,
        AdminVars.SHADOW,
        AdminVars.CARD_BORDER,
        AdminVars.BG,
    ):
        assert var in css, f"{var} missing from CSS"
    # Quasar components are restyled globally so every page inherits the look.
    assert ".q-card" in css
    assert ".admin-header .q-btn" in css  # header text is token-driven, not white


def test_font_is_self_hosted_not_cdn():
    """Wanted Sans is bundled + served locally (#193) — no external CDN."""
    css = build_admin_css()
    assert "@font-face" in css
    assert '"Wanted Sans Variable"' in css
    assert "/admin-static/fonts/WantedSansVariable.woff2" in css
    assert "cdn.jsdelivr.net" not in css  # never reintroduce the CDN dependency
