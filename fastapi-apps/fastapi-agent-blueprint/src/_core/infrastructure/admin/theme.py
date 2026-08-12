"""Centralized theme + style system for the NiceGUI admin dashboard (#193, #365).

Single source of truth for admin colors, **style tokens** (radius, shadow,
border treatment), layout metrics, and the helper CSS classes + Quasar
component overrides that every admin page inherits.

Design (see plan #193, restyled in #365):

* The look is driven by CSS custom properties: ``--q-*`` (Quasar brand) and
  ``--admin-*`` (semantic + style) variables, flipped between light and dark via
  Quasar's ``body--dark`` class — a single toggle, no reload, no per-page
  ``ui.colors()`` call. The two groups are **not** emitted the same way:
  ``--admin-*`` goes on ``:root``, but ``--q-*`` must go on ``body`` with
  ``!important`` to outrank NiceGUI's inline body style. See _BRAND_TOKENS —
  getting this wrong makes the whole brand half of the palette silently inert,
  which is the state this module shipped in from #193 until #365.
* There is **one theme** — a neutral-mono admin look. A fully desaturated grey
  ramp carries the UI, a *single* blue accent marks interactive/active state,
  and three status hues (green/red/amber) are reserved for outcomes. Shape is
  restrained: 8px cards, 6px buttons, hairline borders instead of elevation.
  It is defined as ``_ROOT_TOKENS`` (:root / light) + ``_DARK_TOKENS``
  (``.body--dark`` overrides). To rebrand a fork, edit those token dicts —
  in practice, changing ``AdminColors.PRIMARY`` is enough.
* **Every colour comes from one ramp** — Tailwind (zinc greys, plus
  blue/green/red/amber at the 600 step). This is load-bearing, not cosmetic:
  before #365 the palette mixed a Toss ramp (primary/positive/negative) with a
  Tailwind slate ramp (secondary/warning/info/chart), and two ramps with
  different hue and saturation curves cannot be reconciled by nudging
  individual tokens. Keep new colours on the same ramp.
* The CSS is injected **once, app-wide** via ``ui.add_css(..., shared=True)`` so
  it reaches every page — including login / setup / error, which never render
  ``admin_layout``.

Constants here are intentionally **import-free**; the nicegui + settings imports
are lazy inside :func:`install_admin_theme_css`.
"""

from __future__ import annotations

from typing import Final

EMPTY_DISPLAY: Final = "—"


class AdminColors:
    """Brand/semantic palette constants. Also used by chart builders, whose
    canvas lives outside the ``--admin-*`` CSS-var cascade.

    All values are Tailwind palette steps — one ramp, no mixing (#365).
    """

    PRIMARY: Final = "#2563eb"  # blue-600 — the single accent
    SECONDARY: Final = "#71717a"  # zinc-500
    ACCENT: Final = "#2563eb"  # blue-600
    POSITIVE: Final = "#16a34a"  # green-600
    NEGATIVE: Final = "#dc2626"  # red-600
    WARNING: Final = "#d97706"  # amber-600
    # Deliberately the accent, not sky-600: an "info" hue one step off the
    # primary reads as an inconsistency rather than a distinct semantic.
    INFO: Final = "#2563eb"  # blue-600
    # Chart axis/grid neutrals — mid-tone so they read on both the light and
    # dark content surfaces without client-side dark-mode detection (charts
    # render their own canvas, outside the --admin-* CSS var cascade).
    CHART_AXIS: Final = "#a1a1aa"  # zinc-400
    CHART_GRID: Final = "#a1a1aa33"  # CHART_AXIS @ ~0.2 alpha (hex8)


class AdminVars:
    """Names of the CSS custom properties consumed by the helper classes."""

    # Quasar brand. Emitted under ``body`` with ``!important`` — see _BRAND_TOKENS.
    Q_PRIMARY: Final = "--q-primary"
    Q_SECONDARY: Final = "--q-secondary"
    Q_ACCENT: Final = "--q-accent"
    Q_POSITIVE: Final = "--q-positive"
    Q_NEGATIVE: Final = "--q-negative"
    Q_WARNING: Final = "--q-warning"
    Q_INFO: Final = "--q-info"
    # Quasar's own dark surfaces (menus, dialogs, selects, tooltips) come from
    # these two, not from --admin-*. Left at Quasar's defaults they render
    # #1d1d1d/#121212 against our zinc cards.
    Q_DARK: Final = "--q-dark"
    Q_DARK_PAGE: Final = "--q-dark-page"

    # Chrome (header + sidebar). Defined in both blocks so it flips with dark
    # mode — light mode is white-on-hairline, dark mode drops the chrome to the
    # page colour and separates by border alone.
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
    STAT_CARD_MIN_WIDTH: Final = "--admin-stat-card-min-width"
    FONT: Final = "--admin-font"
    # Flat login backdrop. Was ``--admin-login-gradient`` before #365; renamed
    # because the value is no longer a gradient and a lying token name is worse
    # than a rename. See CHANGELOG § Upgrading.
    LOGIN_BG: Final = "--admin-login-bg"


class AdminMetrics:
    """Layout metrics (numbers, not colors)."""

    # 36px, not 44px: an admin list earns its keep by how many rows fit on one
    # screen. Consumed by components/data.py (GRID_MIN_COL_WIDTH below is the
    # one base_admin_page.py reads).
    GRID_ROW_HEIGHT: Final = 36
    GRID_MIN_COL_WIDTH: Final = 120

    # Stat tiles size to their own text otherwise, so a row of them came out
    # ragged — measured 88px / 64px / 62px for "AI Usage" / "Docs" / "User",
    # which reads as three unrelated boxes rather than one row of metrics.
    STAT_CARD_MIN_WIDTH: Final = 150


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
    STAT_CARD: Final = "admin-stat-card"
    STATUS_DOT: Final = "admin-status-dot"
    SUCCESS_SURFACE: Final = "admin-success-surface"
    GRID: Final = "admin-grid"
    GRID_COMPACT: Final = "admin-grid-compact"
    # Sets no height on purpose: ``c.data_grid(auto_height=True)`` derives one
    # from the row count and sets it inline. Deliberately *not* AG Grid's
    # ``domLayout: "autoHeight"`` — that grows the inner wrapper while the outer
    # NiceGUI element keeps Quasar's computed height, so the grid paints over
    # whatever follows it (#368). See _HELPER_CSS and components/data.py.
    GRID_AUTO: Final = "admin-grid-auto"
    CHART: Final = "admin-chart"
    PAGINATION: Final = "admin-pagination"
    EMPTY_STATE: Final = "admin-empty-state"
    LOGIN_BG: Final = "admin-login-bg"
    LOGIN_CARD: Final = "admin-login-card"
    PRE: Final = "admin-pre"
    HIDDEN: Final = "admin-hidden"


# ── Single theme (neutral mono) ──
# Tokens are emitted directly: _ROOT_TOKENS (+ _LAYOUT_TOKENS) in :root / light,
# _DARK_TOKENS as the .body--dark overrides. No preset selection — edit these
# dicts to rebrand a fork. (A selectable-preset system existed and was removed
# in #235; do not reintroduce it without an ADR.)

# Mode-constant :root tokens (layout metrics, typography).
_LAYOUT_TOKENS: Final = {
    AdminVars.GRID_HEIGHT: "calc(100vh - 240px)",
    AdminVars.GRID_HEIGHT_COMPACT: "calc(100vh - 360px)",
    AdminVars.CHART_HEIGHT: "260px",
    AdminVars.LABEL_COL_WIDTH: "140px",
    AdminVars.STAT_CARD_MIN_WIDTH: f"{AdminMetrics.STAT_CARD_MIN_WIDTH}px",
    # System font stack — no bundled webfont (#365 dropped the self-hosted
    # Wanted Sans and the /admin-static mount that existed only to serve it).
    # Order matters: Latin UI fonts first, then Hangul fallbacks for platforms
    # whose UI font has no Hangul coverage. ``-apple-system`` already resolves
    # Hangul on Apple platforms; ``Segoe UI`` does not, so Windows falls
    # through to Malgun Gothic.
    AdminVars.FONT: (
        '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, '
        '"Helvetica Neue", "Apple SD Gothic Neo", "Malgun Gothic", '
        '"Noto Sans KR", Arial, sans-serif'
    ),
}

# Brand + shape + light chrome + light content — the :root token block.
# (Merged with _LAYOUT_TOKENS in build_admin_css.) Tailwind zinc scale:
# 50 #fafafa · 100 #f4f4f5 · 200 #e4e4e7 · 400 #a1a1aa · 500 #71717a ·
# 700 #3f3f46 · 800 #27272a · 900 #18181b · 950 #09090b.
# Quasar brand palette. **Must** be emitted under ``body`` with ``!important``.
#
# NiceGUI writes its own brand palette as an *inline style* on ``<body>``
# (``--q-primary: #5898d4; --q-secondary: #26a69a; --q-accent: #9c27b0; ...``).
# An inline declaration beats every stylesheet rule regardless of selector
# specificity, so declaring these in ``:root`` — as this module did from #193
# through #365's first pass — is inert: ``html`` carries our value, ``body``
# re-declares NiceGUI's, and every descendant inherits NiceGUI's. The result was
# a *third* palette on screen (pale blue, teal secondary, purple accent, cyan
# info) alongside the ``--admin-*`` greys, which is the larger half of why the
# admin colours never sat right.
#
# ``!important`` in a stylesheet does outrank a normal inline declaration, so
# this keeps the inject-once-app-wide model and needs no per-page
# ``ui.colors()`` call (login / setup / error never render ``admin_layout``).
# Verified against the live page, not assumed — see test_theme.py.
_BRAND_TOKENS: Final = {
    AdminVars.Q_PRIMARY: AdminColors.PRIMARY,
    AdminVars.Q_SECONDARY: AdminColors.SECONDARY,
    AdminVars.Q_ACCENT: AdminColors.ACCENT,
    AdminVars.Q_POSITIVE: AdminColors.POSITIVE,
    AdminVars.Q_NEGATIVE: AdminColors.NEGATIVE,
    AdminVars.Q_WARNING: AdminColors.WARNING,
    AdminVars.Q_INFO: AdminColors.INFO,
    # Align Quasar's own dark surfaces with the zinc ladder.
    AdminVars.Q_DARK: "#18181b",  # zinc-900 — matches SURFACE
    AdminVars.Q_DARK_PAGE: "#09090b",  # zinc-950 — matches BG
}

_ROOT_TOKENS: Final = {
    # Shape / elevation. Cards separate by a hairline border, not by lift —
    # the shadow is a `shadow-sm`-scale hint only.
    AdminVars.RADIUS: "8px",
    AdminVars.RADIUS_BUTTON: "6px",
    AdminVars.SHADOW: "0 1px 2px 0 rgba(0,0,0,0.05)",
    AdminVars.CARD_BORDER: "1px solid var(--admin-border)",
    # Light chrome — white header/sidebar on a zinc-200 hairline. The active nav
    # state is *neutral* (zinc-900 on zinc-100), not accent-tinted: colour is
    # reserved for buttons/links/focus so the sidebar stays quiet.
    AdminVars.HEADER_BG: "#ffffff",
    AdminVars.HEADER_TEXT: "#27272a",  # zinc-800
    AdminVars.DRAWER_BG: "#ffffff",
    AdminVars.DRAWER_TEXT: "#3f3f46",  # zinc-700
    AdminVars.NAV_ACTIVE: "#18181b",  # zinc-900
    AdminVars.NAV_ACTIVE_BG: "#f4f4f5",  # zinc-100
    AdminVars.CHROME_BORDER: "#e4e4e7",  # zinc-200
    # Light content (Tailwind zinc scale).
    AdminVars.BG: "#fafafa",  # zinc-50 — page behind the cards
    AdminVars.SURFACE: "#ffffff",
    AdminVars.BORDER: "#e4e4e7",  # zinc-200
    AdminVars.TEXT_MUTED: "#71717a",  # zinc-500 — secondary text
    AdminVars.SUCCESS_BG: "#f0fdf4",  # green-50
    # Zebra striping is off (#365): on a desaturated ramp the odd-row tint is
    # too weak to track a row by and only reads as banding. Rows separate by
    # the AG Grid row border instead. Kept equal to SURFACE rather than
    # deleted, so the quartz default tint cannot leak back in.
    AdminVars.ROW_ALT: "#ffffff",
    AdminVars.ROW_HOVER: "#f4f4f5",  # zinc-100
    AdminVars.LOGIN_BG: "#fafafa",  # zinc-50 — flat, no gradient
}

# .body--dark overrides. Chrome drops to the page colour (#09090b) and separates
# by border alone, so the only raised surface is the card (#18181b) — an
# elevation ladder of page = chrome < card. Chrome is re-asserted here (else
# dark mode inherits the light chrome).
_DARK_TOKENS: Final = {
    AdminVars.BG: "#09090b",  # zinc-950
    AdminVars.SURFACE: "#18181b",  # zinc-900
    AdminVars.BORDER: "#27272a",  # zinc-800
    AdminVars.SHADOW: "0 1px 2px 0 rgba(0,0,0,0.4)",
    AdminVars.TEXT_MUTED: "#a1a1aa",  # zinc-400
    AdminVars.SUCCESS_BG: "#052e16",  # green-950
    AdminVars.ROW_ALT: "#18181b",  # = SURFACE (striping off)
    AdminVars.ROW_HOVER: "#27272a",  # zinc-800
    AdminVars.HEADER_BG: "#09090b",  # zinc-950
    AdminVars.HEADER_TEXT: "#fafafa",  # zinc-50
    AdminVars.DRAWER_BG: "#09090b",  # zinc-950
    # One step brighter than TEXT_MUTED (zinc-400) on purpose. Both were
    # zinc-400 in #365's first pass, which made the muted treatment on inactive
    # nav icons and on section headers a no-op in dark mode — and because that
    # same pass dropped the old `opacity: 0.5` from `.admin-nav-section`, the
    # dark drawer ended up with *less* hierarchy than before. Pinned by
    # test_drawer_text_and_muted_are_distinct_in_both_modes.
    AdminVars.DRAWER_TEXT: "#d4d4d8",  # zinc-300
    AdminVars.NAV_ACTIVE: "#fafafa",  # zinc-50
    AdminVars.NAV_ACTIVE_BG: "#27272a",  # zinc-800
    AdminVars.CHROME_BORDER: "#27272a",  # zinc-800
    AdminVars.LOGIN_BG: "#09090b",  # zinc-950
}


_HELPER_CSS: Final = """
/* === Helper classes + Quasar component overrides (token-driven) === */
body, .q-page-container {
  background-color: var(--admin-bg) !important;
}
body {
  font-family: var(--admin-font) !important;
}
/* Chrome: header + sidebar, separated from content by a hairline only. */
.admin-header {
  background-color: var(--admin-header-bg) !important;
  color: var(--admin-header-text) !important;
  box-shadow: none !important;
  border-bottom: 1px solid var(--admin-chrome-border);
}
/* `.q-btn__content` is listed on purpose. NiceGUI buttons default to
   `color="primary"`, which Quasar renders as a `text-primary` class on the
   *inner content span* — so styling only `.q-btn` leaves the label accent-blue
   while the icons go neutral (the operator's own username rendered as a link).
   Quasar's `.text-primary` is itself `!important`, so this needs both the
   higher specificity and the `!important` to win. */
.admin-header .q-btn,
.admin-header .q-btn__content,
.admin-header .q-icon,
.admin-brand,
.admin-brand .q-icon {
  color: var(--admin-header-text) !important;
}
.admin-brand {
  font-weight: 600;
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
/* Inactive nav icons carry `.admin-text-muted` (see layout.py `_nav_item`), but
   the rule above is a two-class selector and would outrank the single-class
   helper — the mute would apply to nothing. Restate it at higher specificity.
   Same reason the collapse control's chevron/label read as muted. */
.admin-drawer .q-icon.admin-text-muted,
.admin-drawer .q-item__label.admin-text-muted {
  color: var(--admin-text-muted);
}
.admin-nav-section {
  color: var(--admin-text-muted);
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
  font-weight: 600;
}
.admin-nav-active-item {
  background-color: var(--admin-nav-active-bg);
  border-radius: var(--admin-radius-button);
}
/* The one place colour is spent inside the chrome. */
.admin-accent-icon {
  color: var(--q-primary) !important;
}
/* Content helpers. */
.admin-field-label {
  width: var(--admin-label-col-width);
  font-weight: 500;
  color: var(--admin-text-muted);
}
.admin-text-muted,
.admin-empty-value {
  color: var(--admin-text-muted);
}

.admin-stat-card {
  min-width: var(--admin-stat-card-min-width);
}

/* Replaces the row-selection radio that `c.data_grid` put in this column
   position on the dashboard's infrastructure panel: same glance, but it means
   something and cannot be clicked to no effect. Colour is not the only signal —
   the state word sits beside it. */
.admin-status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex: 0 0 8px;
  background-color: var(--admin-text-muted);
}

.admin-status-dot.admin-status-active {
  background-color: var(--q-positive);
}

.admin-status-dot.admin-status-stub {
  background-color: var(--q-warning);
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
/* Deliberately sets no height: `c.data_grid(auto_height=True)` derives one from
   the row count and sets it inline, so this class must not supply a competing
   value. (AG Grid's own `domLayout: "autoHeight"` was tried and does not work
   in the NiceGUI embed — the inner wrapper grows past the outer element and
   paints over the next section. See components/data.py.) */
.admin-grid-auto {
  width: 100%;
}
/* AG Grid v33 Theming API: params map to --ag-<kebab-case>. `rowBorder`
   supersedes the legacy --ag-row-border-{color,style,width} trio.

   `--ag-background-color` is load-bearing, not cosmetic. Without it the grid
   keeps the quartz palette's own surface while every other panel uses
   --admin-surface, so in dark mode the grid floated as a lighter slab — and
   worse, pinning only the odd row to --admin-row-alt then made striping
   *reappear inverted* (odd rows darker than the quartz base). Both surfaces
   have to come from the same token or neither should.

   Striping is pinned to the surface colour rather than deleted so the quartz
   default odd-row tint cannot leak back in; rows separate by border (#365). */
.admin-grid,
.admin-grid-compact,
.admin-grid-auto {
  --ag-background-color: var(--admin-surface);
  --ag-header-background-color: var(--admin-bg);
  --ag-odd-row-background-color: var(--admin-row-alt);
  --ag-row-hover-color: var(--admin-row-hover);
  --ag-row-border: 1px solid var(--admin-border);
  --ag-border-color: var(--admin-border);
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
.admin-grid-compact .ag-header-cell,
.admin-grid-auto .ag-cell,
.admin-grid-auto .ag-row,
.admin-grid-auto .ag-header-cell {
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
  background: var(--admin-login-bg) !important;
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
/* === State transitions (palette-independent) ===
   Restrained by design (#365): state changes are communicated by colour and
   border, never by moving the element — hover-lift and press-squish read as
   dated on a data-dense admin surface. Pinned by test_no_lift_on_hover, which
   scans this payload for movement primitives, so do not name them even in a
   comment here. Honors prefers-reduced-motion. */
.q-card {
  transition: border-color 140ms ease, background-color 140ms ease;
}
.q-card.cursor-pointer:hover {
  border-color: var(--admin-text-muted) !important;
}
.q-btn {
  transition: background-color 140ms ease, border-color 140ms ease,
    filter 140ms ease;
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
  .q-btn,
  .admin-drawer .q-item,
  .admin-grid .ag-row,
  .admin-grid-compact .ag-row,
  .q-field--outlined .q-field__control {
    transition: none !important;
  }
}
"""


def _emit_vars(mapping: dict[str, str]) -> str:
    return "\n".join(f"  {name}: {value};" for name, value in mapping.items())


def _emit_vars_important(mapping: dict[str, str]) -> str:
    """Emit custom properties with ``!important`` (to beat an inline style)."""
    return "\n".join(
        f"  {name}: {value} !important;" for name, value in mapping.items()
    )


def build_admin_css() -> str:
    """Return the single CSS payload injected app-wide for the admin theme.

    Pure string builder (no nicegui import). Emits, in order:

    1. ``body`` — the Quasar ``--q-*`` brand palette with ``!important``, which
       is what lets it outrank NiceGUI's inline body style (see _BRAND_TOKENS).
    2. ``:root`` — shape + light chrome + light content + layout metrics.
    3. ``.body--dark`` — the dark overrides.
    4. The helper CSS.

    No ``@font-face`` — the stack in :data:`AdminVars.FONT` resolves against
    fonts the OS already has.
    """
    root_vars = {**_ROOT_TOKENS, **_LAYOUT_TOKENS}
    return (
        "/* === Admin theme (neutral mono) === */\n"
        "/* Brand palette: !important is load-bearing — NiceGUI sets --q-* as an\n"
        "   inline style on <body>, which no plain selector can outrank. */\n"
        "body {\n" + _emit_vars_important(_BRAND_TOKENS) + "\n}\n"
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
