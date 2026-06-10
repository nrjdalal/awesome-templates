"""Centralized theme + style system for the NiceGUI admin dashboard (#193).

Single source of truth for admin colors, **style tokens** (radius, shadow,
border treatment), layout metrics, and the helper CSS classes + Quasar
component overrides that every admin page inherits.

Design (see plan #193):

* The look is driven by CSS custom properties: ``--q-*`` (Quasar brand) and
  ``--admin-*`` (semantic + style) variables, flipped between light and dark via
  Quasar's ``body--dark`` class — a single toggle, no reload, no per-page
  ``ui.colors()`` call.
* There is **one theme** — a Toss Design System look (calm blue accent, TDS grey
  scale, generous/pill radius, soft elevation, light-in-light-mode chrome). It is
  defined directly as ``_ROOT_TOKENS`` (:root / light) + ``_DARK_TOKENS``
  (``.body--dark`` overrides). To rebrand a fork, edit those token dicts.
* The CSS is injected **once, app-wide** via ``ui.add_css(..., shared=True)`` so
  it reaches every page — including login / setup / error.

Constants here are intentionally **import-free**; the nicegui + settings imports
are lazy inside :func:`install_admin_theme_css`.
"""

from __future__ import annotations

from typing import Final

EMPTY_DISPLAY: Final = "—"


class AdminColors:
    """Brand/semantic palette constants (Toss Design System). Also used by chart
    builders, whose canvas lives outside the ``--admin-*`` CSS-var cascade."""

    PRIMARY: Final = "#3182f6"  # TDS blue
    SECONDARY: Final = "#64748b"
    ACCENT: Final = "#3182f6"
    POSITIVE: Final = "#15c47e"  # TDS green
    NEGATIVE: Final = "#f04452"  # TDS red
    WARNING: Final = "#d97706"
    INFO: Final = "#0284c7"
    # Chart axis/grid neutrals — mid-tone so they read on both the light and
    # dark content surfaces without client-side dark-mode detection (charts
    # render their own canvas, outside the --admin-* CSS var cascade).
    CHART_AXIS: Final = "#94a3b8"
    CHART_GRID: Final = "#94a3b833"  # CHART_AXIS @ ~0.2 alpha (hex8)


class AdminVars:
    """Names of the CSS custom properties consumed by the helper classes."""

    # Quasar brand.
    Q_PRIMARY: Final = "--q-primary"
    Q_SECONDARY: Final = "--q-secondary"
    Q_ACCENT: Final = "--q-accent"
    Q_POSITIVE: Final = "--q-positive"
    Q_NEGATIVE: Final = "--q-negative"
    Q_WARNING: Final = "--q-warning"
    Q_INFO: Final = "--q-info"

    # Chrome (header + sidebar). Dark + constant for most presets; the ``toss``
    # preset flips these light/dark (light sidebar in light mode) via its
    # light/dark override blocks.
    HEADER_BG: Final = "--admin-header-bg"
    HEADER_TEXT: Final = "--admin-header-text"
    DRAWER_BG: Final = "--admin-drawer-bg"
    DRAWER_TEXT: Final = "--admin-drawer-text"
    NAV_ACTIVE: Final = "--admin-nav-active"
    NAV_ACTIVE_BG: Final = "--admin-nav-active-bg"
    CHROME_BORDER: Final = "--admin-chrome-border"

    # Content surfaces — flip with dark mode.
    BG: Final = "--admin-bg"
    SURFACE: Final = "--admin-surface"
    BORDER: Final = "--admin-border"
    TEXT_MUTED: Final = "--admin-text-muted"
    SUCCESS_BG: Final = "--admin-success-bg"
    ROW_ALT: Final = "--admin-row-alt"
    ROW_HOVER: Final = "--admin-row-hover"

    # Style tokens (shape/elevation).
    RADIUS: Final = "--admin-radius"
    RADIUS_BUTTON: Final = "--admin-radius-button"
    SHADOW: Final = "--admin-shadow"
    CARD_BORDER: Final = "--admin-card-border"

    # Layout metrics + typography.
    GRID_HEIGHT: Final = "--admin-grid-height"
    GRID_HEIGHT_COMPACT: Final = "--admin-grid-height-compact"
    CHART_HEIGHT: Final = "--admin-chart-height"
    LABEL_COL_WIDTH: Final = "--admin-label-col-width"
    FONT: Final = "--admin-font"
    LOGIN_GRADIENT: Final = "--admin-login-gradient"


class AdminMetrics:
    """Layout metrics (numbers, not colors)."""

    GRID_ROW_HEIGHT: Final = 44
    GRID_MIN_COL_WIDTH: Final = 120


class AdminClasses:
    """Helper CSS class names (all ``admin-`` prefixed for the AST guard)."""

    HEADER: Final = "admin-header"
    BRAND: Final = "admin-brand"
    DRAWER: Final = "admin-drawer"
    NAV_SECTION: Final = "admin-nav-section"
    NAV_ACTIVE: Final = "admin-nav-active"
    NAV_ACTIVE_ITEM: Final = "admin-nav-active-item"
    ACCENT_ICON: Final = "admin-accent-icon"
    CARD: Final = "admin-card"
    FIELD_LABEL: Final = "admin-field-label"
    FIELD_VALUE: Final = "admin-field-value"
    MUTED: Final = "admin-text-muted"
    EMPTY_VALUE: Final = "admin-empty-value"
    SUCCESS_SURFACE: Final = "admin-success-surface"
    GRID: Final = "admin-grid"
    GRID_COMPACT: Final = "admin-grid-compact"
    CHART: Final = "admin-chart"
    PAGINATION: Final = "admin-pagination"
    EMPTY_STATE: Final = "admin-empty-state"
    LOGIN_BG: Final = "admin-login-bg"
    LOGIN_CARD: Final = "admin-login-card"
    PRE: Final = "admin-pre"
    HIDDEN: Final = "admin-hidden"


# ── Single theme (Toss Design System) ──
# Tokens are emitted directly: _ROOT_TOKENS (+ _LAYOUT_TOKENS) in :root / light,
# _DARK_TOKENS as the .body--dark overrides. No preset selection — edit these
# dicts to rebrand a fork.

# Mode-constant :root tokens (layout metrics, typography, light login backdrop).
_LAYOUT_TOKENS: Final = {
    AdminVars.GRID_HEIGHT: "calc(100vh - 240px)",
    AdminVars.GRID_HEIGHT_COMPACT: "calc(100vh - 360px)",
    AdminVars.CHART_HEIGHT: "260px",
    AdminVars.LABEL_COL_WIDTH: "160px",
    # Wanted Sans (self-hosted, see _FONT_FACE_CSS) with a graceful system-font
    # fallback — so the UI still renders cleanly if the asset fails to load.
    AdminVars.FONT: (
        '"Wanted Sans Variable", -apple-system, BlinkMacSystemFont, '
        '"Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif'
    ),
    # Soft pastel-blue login backdrop (light). The dark variant is in _DARK_TOKENS.
    AdminVars.LOGIN_GRADIENT: "linear-gradient(160deg, #eaf2ff 0%, #cfe0fb 100%)",
}

# Wanted Sans webfont (open-sourced by Wanted, SIL OFL 1.1) — self-hosted from
# the repo (src/_apps/admin/static/fonts/), served at /admin-static by
# bootstrap_admin(). No external CDN dependency. The AdminVars.FONT stack falls
# back to system fonts if the asset is missing, so the UI degrades gracefully.
_FONT_FACE_CSS: Final = """
@font-face {
  font-family: "Wanted Sans Variable";
  font-style: normal;
  font-weight: 400 1000;
  font-display: swap;
  src: url("/admin-static/fonts/WantedSansVariable.woff2") format("woff2-variations");
}
"""

# Brand + shape + light chrome + light content — the :root token block.
# (Merged with _LAYOUT_TOKENS in build_admin_css.) TDS grey scale: 50 #f9fafb ·
# 100 #f2f4f6 · 200 #e5e8eb · 500 #8b95a1 · 700 #4e5968 · 800 #333d4b · 900 #191f28.
_ROOT_TOKENS: Final = {
    # Brand (Quasar --q-*).
    AdminVars.Q_PRIMARY: AdminColors.PRIMARY,
    AdminVars.Q_SECONDARY: AdminColors.SECONDARY,
    AdminVars.Q_ACCENT: AdminColors.ACCENT,
    AdminVars.Q_POSITIVE: AdminColors.POSITIVE,
    AdminVars.Q_NEGATIVE: AdminColors.NEGATIVE,
    AdminVars.Q_WARNING: AdminColors.WARNING,
    AdminVars.Q_INFO: AdminColors.INFO,
    # Shape / elevation.
    AdminVars.RADIUS: "20px",  # very rounded cards/inputs/grid
    AdminVars.RADIUS_BUTTON: "9999px",  # near-pill buttons (clamps to half-height)
    AdminVars.SHADOW: (
        "0 4px 14px rgba(49,130,246,0.06), 0 1px 3px rgba(15,23,42,0.06)"
    ),
    AdminVars.CARD_BORDER: "1px solid var(--admin-border)",
    # Light chrome — Toss is white-dominant: white header/sidebar, dark text,
    # blue active state, grey-200 hairline. Flips dark in _DARK_TOKENS.
    AdminVars.HEADER_BG: "#ffffff",
    AdminVars.HEADER_TEXT: "#333d4b",  # grey 800
    AdminVars.DRAWER_BG: "#ffffff",
    AdminVars.DRAWER_TEXT: "#4e5968",  # grey 700
    AdminVars.NAV_ACTIVE: "#3182f6",
    AdminVars.NAV_ACTIVE_BG: "rgba(49,130,246,0.10)",
    AdminVars.CHROME_BORDER: "#e5e8eb",  # grey 200
    # Light content (TDS grey scale).
    AdminVars.BG: "#f2f4f6",  # grey 100 — grouped-page background
    AdminVars.SURFACE: "#ffffff",
    AdminVars.BORDER: "#e5e8eb",  # grey 200
    AdminVars.TEXT_MUTED: "#8b95a1",  # grey 500 — secondary text
    AdminVars.SUCCESS_BG: "#e8f8f0",  # tint of TDS green #15c47e
    AdminVars.ROW_ALT: "#f9fafb",  # grey 50
    AdminVars.ROW_HOVER: "#f2f4f6",  # grey 100
}

# .body--dark overrides. Shadows barely read on dark, so cards separate by an
# elevation ladder (page #14161b < chrome #191f28 < card #262b35) + a black-based
# shadow. Chrome is re-asserted here (else dark mode inherits the light chrome).
_DARK_TOKENS: Final = {
    AdminVars.BG: "#14161b",
    AdminVars.SURFACE: "#262b35",
    AdminVars.BORDER: "#3a4150",
    AdminVars.SHADOW: "0 2px 8px rgba(0,0,0,0.45)",
    AdminVars.TEXT_MUTED: "#8b95a1",  # grey 500
    AdminVars.SUCCESS_BG: "#103a2a",
    AdminVars.ROW_ALT: "#21252e",
    AdminVars.ROW_HOVER: "#2f3540",
    AdminVars.HEADER_BG: "#191f28",  # grey 900
    AdminVars.HEADER_TEXT: "#e5e7eb",
    AdminVars.DRAWER_BG: "#191f28",
    AdminVars.DRAWER_TEXT: "#cbd2e0",
    AdminVars.NAV_ACTIVE: "#6aa4f8",
    AdminVars.NAV_ACTIVE_BG: "rgba(255,255,255,0.10)",
    AdminVars.CHROME_BORDER: "rgba(255,255,255,0.06)",
    # Dark login backdrop — soft deep blue→charcoal, mode-matched to the pastel.
    AdminVars.LOGIN_GRADIENT: "linear-gradient(160deg, #222c40 0%, #161922 100%)",
}


_HELPER_CSS: Final = """
/* === Helper classes + Quasar component overrides (token-driven) === */
body, .q-page-container {
  background-color: var(--admin-bg) !important;
}
body {
  font-family: var(--admin-font) !important;
}
/* Chrome: dark header + sidebar, light text. */
.admin-header {
  background-color: var(--admin-header-bg) !important;
  color: var(--admin-header-text) !important;
  box-shadow: none !important;
  border-bottom: 1px solid var(--admin-chrome-border);
}
.admin-header .q-btn,
.admin-header .q-icon,
.admin-brand,
.admin-brand .q-icon {
  color: var(--admin-header-text) !important;
}
.admin-brand {
  font-weight: 700;
}
.admin-drawer {
  background-color: var(--admin-drawer-bg) !important;
  color: var(--admin-drawer-text) !important;
  border-right: 1px solid var(--admin-chrome-border);
}
.admin-drawer .q-item,
.admin-drawer .q-item__label,
.admin-drawer .q-icon {
  color: var(--admin-drawer-text);
}
.admin-nav-section {
  color: var(--admin-drawer-text);
  opacity: 0.5;
  font-size: 0.68rem;
  letter-spacing: 0.09em;
  text-transform: uppercase;
  font-weight: 600;
}
/* Collapsed mini rail: hide section headers (raw labels Quasar can't auto-hide)
   so they don't overflow the narrow icon-only rail. */
.q-drawer--mini .admin-nav-section {
  display: none;
}
.admin-nav-active,
.admin-drawer .admin-nav-active,
.admin-drawer .admin-nav-active .q-icon {
  color: var(--admin-nav-active) !important;
  font-weight: 700;
}
.admin-nav-active-item {
  background-color: var(--admin-nav-active-bg);
  border-radius: var(--admin-radius);
}
.admin-accent-icon {
  color: var(--admin-nav-active) !important;
}
/* Content helpers. */
.admin-field-label {
  width: var(--admin-label-col-width);
  font-weight: 700;
}
.admin-text-muted,
.admin-empty-value {
  color: var(--admin-text-muted);
}
.admin-success-surface {
  background-color: var(--admin-success-bg) !important;
}
.admin-grid {
  width: 100%;
  height: var(--admin-grid-height);
}
.admin-grid-compact {
  width: 100%;
  height: var(--admin-grid-height-compact);
}
.admin-grid,
.admin-grid-compact {
  --ag-odd-row-background-color: var(--admin-row-alt);
  --ag-row-hover-color: var(--admin-row-hover);
  --ag-border-radius: var(--admin-radius);
}
/* AG Grid v33 hides cells via `:where(.ag-delay-render) ... { visibility:hidden }`
   until its first render completes, then drops `ag-delay-render`. In the NiceGUI
   embed that class can get stuck (the grid initializes before its container is
   laid out), leaving rows permanently invisible — data is in the DOM but the
   grid looks empty. Force our admin grids' cells visible; the zero-specificity
   `:where()` rule cannot win against this. */
.admin-grid .ag-cell,
.admin-grid .ag-row,
.admin-grid .ag-header-cell,
.admin-grid-compact .ag-cell,
.admin-grid-compact .ag-row,
.admin-grid-compact .ag-header-cell {
  visibility: visible !important;
}
.admin-chart {
  width: 100%;
  height: var(--admin-chart-height);
}
.admin-pagination {
  justify-content: flex-end;
}
.admin-empty-state {
  color: var(--admin-text-muted);
  align-items: center;
  text-align: center;
  padding: 48px 0;
}
.admin-login-bg,
.admin-login-bg .q-page-container {
  background: var(--admin-login-gradient) !important;
}
.admin-login-card {
  width: 360px;
  max-width: 92vw;
}
.admin-pre {
  white-space: pre-wrap;
}
.admin-hidden {
  display: none;
}
/* Shape/elevation on standard Quasar components. The surface token drives the
   card background (except success surfaces, which keep their own tint) so the
   light/dark surface colors actually apply instead of Quasar's defaults. */
.q-card:not(.admin-success-surface) {
  background-color: var(--admin-surface) !important;
}
.q-card {
  border-radius: var(--admin-radius) !important;
  box-shadow: var(--admin-shadow) !important;
  border: var(--admin-card-border) !important;
}
.q-btn {
  border-radius: var(--admin-radius-button);
}
.q-field--outlined .q-field__control,
.q-field__control {
  border-radius: var(--admin-radius);
}
/* === Micro-interactions (palette-independent) ===
   Toss-grade tactile feedback: clickable cards lift on hover, buttons squish on
   press, nav/rows/inputs ease their state changes. Hover-lift is scoped to
   `.cursor-pointer` cards (set by c.card(clickable_to=...)) so static content
   cards never drift. Honors prefers-reduced-motion. */
.q-card {
  transition: box-shadow 160ms ease, transform 160ms ease, border-color 160ms ease;
}
.q-card.cursor-pointer:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 24px rgba(15,23,42,0.12);
}
.q-card.cursor-pointer:active {
  transform: translateY(0);
}
.q-btn {
  transition: transform 120ms ease, box-shadow 160ms ease, filter 160ms ease;
}
.q-btn:active {
  transform: translateY(1px) scale(0.985);
}
.admin-drawer .q-item {
  transition: background-color 140ms ease, color 140ms ease;
}
.admin-grid .ag-row,
.admin-grid-compact .ag-row {
  transition: background-color 120ms ease;
}
.q-field--outlined .q-field__control {
  transition: border-color 140ms ease, box-shadow 140ms ease;
}
@media (prefers-reduced-motion: reduce) {
  .q-card,
  .q-card.cursor-pointer:hover,
  .q-card.cursor-pointer:active,
  .q-btn,
  .q-btn:active,
  .admin-drawer .q-item,
  .admin-grid .ag-row,
  .admin-grid-compact .ag-row,
  .q-field--outlined .q-field__control {
    transition: none !important;
    transform: none !important;
  }
}
"""


def _emit_vars(mapping: dict[str, str]) -> str:
    return "\n".join(f"  {name}: {value};" for name, value in mapping.items())


def build_admin_css() -> str:
    """Return the single CSS payload injected app-wide for the admin theme.

    Pure string builder (no nicegui import). Emits ``:root`` (brand + shape +
    light chrome + light content + layout) and ``.body--dark`` (dark overrides),
    then the helper CSS.
    """
    root_vars = {**_ROOT_TOKENS, **_LAYOUT_TOKENS}
    return (
        _FONT_FACE_CSS + "/* === Admin theme (Toss Design System) === */\n"
        ":root {\n" + _emit_vars(root_vars) + "\n}\n"
        ".body--dark {\n" + _emit_vars(_DARK_TOKENS) + "\n}\n" + _HELPER_CSS
    )


_theme_css_installed = False


def install_admin_theme_css() -> None:
    """Inject the admin theme CSS app-wide (once per process).

    Calls ``ui.add_css(..., shared=True)`` so the stylesheet lands in every
    page's ``<head>`` — including login / setup / error which never render
    :func:`admin_layout`. Guarded so repeated ``bootstrap_admin()`` calls (test
    reloads) do not double-inject.
    """
    global _theme_css_installed
    if _theme_css_installed:
        return
    from nicegui import ui

    ui.add_css(build_admin_css(), shared=True)
    _theme_css_installed = True
