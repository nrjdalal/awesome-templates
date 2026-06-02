"""Centralized theme + style system for the NiceGUI admin dashboard (#193).

Single source of truth for admin colors, **style tokens** (radius, shadow,
border treatment), layout metrics, and the helper CSS classes + Quasar
component overrides that every admin page inherits.

Design (see plan #193 / Codex cross-review):

* The look is driven by CSS custom properties: ``--q-*`` (Quasar brand) and
  ``--admin-*`` (semantic + style) variables. The shell **chrome** (header +
  sidebar) is dark and constant; the **content** area is light and flips to
  dark via Quasar's ``body--dark`` class — a single toggle, no reload, no
  per-page ``ui.colors()`` call.
* Multiple **style presets** (``default``, ``linear``, ``shadcn``,
  ``supabase``) bundle a full token set, selected at boot via
  ``ADMIN_THEME_PALETTE``. They share the dark-chrome + light-content structure
  and differ mainly in accent color, radius and elevation.
* The CSS is injected **once, app-wide** via ``ui.add_css(..., shared=True)`` so
  it reaches every page — including login / setup / error.

Constants here are intentionally **import-free**; the nicegui + settings imports
are lazy inside :func:`install_admin_theme_css`.
"""

from __future__ import annotations

from typing import Final

EMPTY_DISPLAY: Final = "—"


class AdminColors:
    """Default brand palette constants (referenced by the ``default`` preset)."""

    PRIMARY: Final = "#5b5bd6"
    SECONDARY: Final = "#64748b"
    ACCENT: Final = "#6366f1"
    POSITIVE: Final = "#16a34a"
    NEGATIVE: Final = "#dc2626"
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

    # Chrome (header + sidebar) — dark and constant across light/dark mode.
    HEADER_BG: Final = "--admin-header-bg"
    HEADER_TEXT: Final = "--admin-header-text"
    DRAWER_BG: Final = "--admin-drawer-bg"
    DRAWER_TEXT: Final = "--admin-drawer-text"
    NAV_ACTIVE: Final = "--admin-nav-active"
    NAV_ACTIVE_BG: Final = "--admin-nav-active-bg"

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
    SHADOW: Final = "--admin-shadow"
    CARD_BORDER: Final = "--admin-card-border"

    # Layout metrics + typography.
    GRID_HEIGHT: Final = "--admin-grid-height"
    GRID_HEIGHT_COMPACT: Final = "--admin-grid-height-compact"
    CHART_HEIGHT: Final = "--admin-chart-height"
    LABEL_COL_WIDTH: Final = "--admin-label-col-width"
    FONT: Final = "--admin-font"


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


# ── Style presets (#193) ──
#
# "chrome": dark header/sidebar tokens + brand + shape — emitted in :root only
#   (constant across light/dark mode; the sidebar stays dark either way).
# "light"/"dark": content surfaces that flip with Quasar's body--dark.
DEFAULT_PALETTE: Final = "default"

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

# Neutral charcoal dark surfaces (not blue-navy) so the content area is
# cohesive with the neutral/charcoal chrome of the shadcn / supabase / linear
# presets (the prior navy tones clashed). Deliberately lifted off pure black
# (a near-OLED #09090b read as harsh) into a soft charcoal, with a three-step
# elevation — page (darkest) < chrome (#18181b) < card — so cards separate
# without relying on contrast alone.
_CONTENT_DARK: Final = {
    AdminVars.BG: "#131316",
    AdminVars.SURFACE: "#1f1f24",
    AdminVars.BORDER: "#323239",
    AdminVars.TEXT_MUTED: "#a1a1aa",
    AdminVars.SUCCESS_BG: "#16311f",
    AdminVars.ROW_ALT: "#1a1a1f",
    AdminVars.ROW_HOVER: "#27272e",
}

_CONTENT_LIGHT: Final = {
    AdminVars.BG: "#f7f8fa",
    AdminVars.SURFACE: "#ffffff",
    AdminVars.BORDER: "#e5e7eb",
    AdminVars.TEXT_MUTED: "#6b7280",
    AdminVars.SUCCESS_BG: "#f0fdf4",
    AdminVars.ROW_ALT: "#f8fafc",
    AdminVars.ROW_HOVER: "#f1f5f9",
}


def _chrome(
    *,
    primary: str,
    accent: str,
    nav_active: str,
    header_bg: str,
    radius: str,
    shadow: str,
    card_border: str,
    negative: str = AdminColors.NEGATIVE,
) -> dict[str, str]:
    """Build a preset's :root token block (dark chrome + brand + shape)."""
    return {
        AdminVars.Q_PRIMARY: primary,
        AdminVars.Q_SECONDARY: AdminColors.SECONDARY,
        AdminVars.Q_ACCENT: accent,
        AdminVars.Q_POSITIVE: AdminColors.POSITIVE,
        AdminVars.Q_NEGATIVE: negative,
        AdminVars.Q_WARNING: AdminColors.WARNING,
        AdminVars.Q_INFO: AdminColors.INFO,
        AdminVars.HEADER_BG: header_bg,
        AdminVars.HEADER_TEXT: "#e5e7eb",
        AdminVars.DRAWER_BG: header_bg,
        AdminVars.DRAWER_TEXT: "#cbd2e0",
        AdminVars.NAV_ACTIVE: nav_active,
        AdminVars.NAV_ACTIVE_BG: "rgba(255,255,255,0.10)",
        AdminVars.RADIUS: radius,
        AdminVars.SHADOW: shadow,
        AdminVars.CARD_BORDER: card_border,
    }


_PALETTES: Final = {
    # Indigo on navy chrome — the default modern look.
    "default": {
        "chrome": _chrome(
            primary=AdminColors.PRIMARY,
            accent=AdminColors.ACCENT,
            nav_active="#a5b4fc",
            header_bg="#1a1d2e",
            radius="10px",
            shadow="0 1px 3px rgba(0,0,0,0.08)",
            card_border="1px solid var(--admin-border)",
        ),
    },
    # Linear / Vercel — flat, border-based, indigo-violet.
    "linear": {
        "chrome": _chrome(
            primary="#5e6ad2",
            accent="#5e6ad2",
            nav_active="#8b87ff",
            header_bg="#0d0d0f",
            radius="6px",
            shadow="none",
            card_border="1px solid var(--admin-border)",
            negative="#eb5757",
        ),
    },
    # shadcn / Notion — rounded, soft shadow, indigo accent.
    "shadcn": {
        "chrome": _chrome(
            primary="#6366f1",
            accent="#6366f1",
            nav_active="#a5b4fc",
            header_bg="#18181b",
            radius="14px",
            shadow="0 1px 3px 0 rgba(0,0,0,0.1), 0 1px 2px -1px rgba(0,0,0,0.1)",
            card_border="1px solid var(--admin-border)",
            negative="#ef4444",
        ),
    },
    # Supabase / Stripe — green accent, charcoal chrome.
    "supabase": {
        "chrome": _chrome(
            primary="#3ecf8e",
            accent="#3ecf8e",
            nav_active="#3ecf8e",
            header_bg="#1c1c1c",
            radius="8px",
            shadow="0 1px 2px rgba(0,0,0,0.08)",
            card_border="1px solid var(--admin-border)",
            negative="#ef4444",
        ),
    },
}

PALETTES: Final = tuple(_PALETTES)


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
  border-bottom: 1px solid rgba(255,255,255,0.06);
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
  border-right: 1px solid rgba(255,255,255,0.06);
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
  background: linear-gradient(135deg, #1e1b4b 0%, #0f172a 100%) !important;
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
  border-radius: var(--admin-radius);
}
.q-field--outlined .q-field__control,
.q-field__control {
  border-radius: var(--admin-radius);
}
"""


def palette_accent(palette: str = DEFAULT_PALETTE) -> str:
    """Return the selected preset's primary/accent color.

    Used by chart builders whose canvas lives outside the CSS-var cascade, so a
    palette-driven element (e.g. a bar fill) still tracks ``ADMIN_THEME_PALETTE``
    instead of hardcoding the default-preset accent. Unknown names fall back to
    :data:`DEFAULT_PALETTE`.
    """
    name = palette if palette in _PALETTES else DEFAULT_PALETTE
    return _PALETTES[name]["chrome"][AdminVars.Q_PRIMARY]


def _emit_vars(mapping: dict[str, str]) -> str:
    return "\n".join(f"  {name}: {value};" for name, value in mapping.items())


def build_admin_css(palette: str = DEFAULT_PALETTE) -> str:
    """Return the single CSS payload injected app-wide for the admin theme.

    Pure string builder (no nicegui import). Emits ``:root`` (dark chrome +
    brand + shape + light content) and ``.body--dark`` (content dark overrides)
    blocks for the selected preset, then the palette-independent helper CSS.
    Unknown palette names fall back to :data:`DEFAULT_PALETTE`.
    """
    name = palette if palette in _PALETTES else DEFAULT_PALETTE
    root_vars = {
        **_PALETTES[name]["chrome"],
        **_CONTENT_LIGHT,
        **_LAYOUT_TOKENS,
    }
    return (
        _FONT_FACE_CSS + f"/* === Admin theme (#193) — palette: {name} === */\n"
        ":root {\n" + _emit_vars(root_vars) + "\n}\n"
        ".body--dark {\n" + _emit_vars(_CONTENT_DARK) + "\n}\n" + _HELPER_CSS
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

    from src._core.config import settings

    ui.add_css(build_admin_css(settings.admin_theme_palette), shared=True)
    _theme_css_installed = True
