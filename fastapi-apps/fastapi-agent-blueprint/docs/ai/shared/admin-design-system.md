# Admin Design System

How to build NiceGUI admin pages so they share one consistent, modern look and
stay easy to extend. Introduced with #193.

## Principles

- **Intuitive over classic.** Favor clear hierarchy, whitespace, and modern
  affordances over dense, rigid forms.
- **Token-driven.** All color / shape / elevation / typography come from
  `theme.py` tokens. Pages reference `AdminClasses` / `AdminMetrics` or Quasar
  semantic props (`color=primary`, `text-negative`) — **never** raw hex or
  Quasar palette classes (`bg-blue-800`, `text-grey-7`, …). This is enforced by
  `tests/unit/_core/infrastructure/admin/test_no_hardcoded_styles.py`.
- **One implementation per shape.** Every repeated UI shape has exactly one
  builder in the component library. If you reach for `ui.card()` / `ui.dialog()`
  / `ui.aggrid()` directly in a page, check the catalog first.
- **Small, sharp set.** Prefer extending an existing builder's kwargs over
  adding a near-duplicate. A new builder needs a second real call site.

## Layering

```
theme.py            tokens (AdminColors / AdminVars / AdminMetrics / AdminClasses)
   ▲ consumed by    + build_admin_css() (single theme, no bundled webfont)
components/         builders — the ONLY place tokens become elements
   ▲ consumed by
base_admin_page.py  layout.py        interface/admin + _apps/admin pages
```

The dependency is one-directional: `components/` consumes `theme.py`; pages and
`BaseAdminPage` consume `components/`. **Components must never import
`base_admin_page`** (cycle). Value formatting / masking / column selection stay
in the caller; builders only render what they are given.

## Theme, motion & focus

- **One theme (neutral mono).** There is no preset selection — the look is
  defined directly as token dicts in `theme.py`: `_BRAND_TOKENS` (the Quasar
  `--q-*` palette, emitted under `body`), `_ROOT_TOKENS` (shape + light chrome +
  light content, emitted in `:root` with `_LAYOUT_TOKENS`) and `_DARK_TOKENS`
  (the `.body--dark` overrides). `build_admin_css()` takes no arguments. To
  rebrand a fork, changing `AdminColors.PRIMARY` is usually enough. The look: a
  desaturated Tailwind **zinc** ramp (`--admin-bg` `#fafafa`, `--admin-border`
  `#e4e4e7`, `--admin-text-muted` `#71717a`), a **single** blue accent
  (`#2563eb`) for interactive/active state, three status hues reserved for
  outcomes (`#16a34a` / `#dc2626` / `#d97706`), a **light-mode chrome flip**
  (white sidebar/header + dark text in light mode, chrome re-asserted in
  `.body--dark`), `8px` cards with `6px` buttons, and a **flat login backdrop**.
  Standalone pages without the shell (login) render the shared
  `render_dark_mode_toggle()` from `layout.py` so light/dark works pre-auth.
- **Every colour comes from one ramp.** All `AdminColors` values are Tailwind
  steps, pinned by `test_palette_is_on_a_single_ramp`. This is not tidiness:
  before #365 the palette mixed a Toss ramp with a Tailwind slate ramp, and two
  ramps with different hue/saturation curves cannot be reconciled by nudging
  individual tokens. Put a new colour on the same ramp or it will read wrong.
- **`--q-*` must be emitted under `body` with `!important`.** NiceGUI writes its
  own brand palette as an **inline style on `<body>`** (`--q-primary: #5898d4`,
  teal secondary, purple accent, cyan info). An inline declaration outranks
  every stylesheet rule regardless of specificity, so a `--q-*` declaration in
  `:root` is **inert** — which is what shipped from #193 until #365, leaving
  every button, badge and `text-primary` on NiceGUI's defaults beside the
  `--admin-*` greys. `!important` in a stylesheet does outrank a normal inline
  declaration, so `_BRAND_TOKENS` keeps the inject-once model with no per-page
  `ui.colors()` call. Pinned by
  `test_brand_palette_is_emitted_on_body_with_important`. If a Quasar-coloured
  control ever renders the wrong colour, check this first.
- **Dark mode separates by border, not elevation or shadow.** `_DARK_TOKENS`
  drops chrome to the page colour (`#09090b`) so the card (`#18181b`) is the only
  raised surface, and the separator is `--admin-chrome-border` / `--admin-border`
  rather than a shadow. `--admin-shadow` is a `shadow-sm`-scale hint in both
  modes; don't lean on it for separation. `--q-dark` / `--q-dark-page` are set
  too, so Quasar's *own* dark surfaces (menus, dialogs, selects, tooltips) land
  on the same zinc ladder instead of `#1d1d1d` / `#121212`.
- **Style tokens.** `--admin-chrome-border` (chrome separator — re-declared in
  `_DARK_TOKENS` since the chrome flips), `--admin-radius-button` (button
  radius), `--admin-login-bg` (flat login backdrop, set per mode). Charts read
  `AdminColors.PRIMARY` / `CHART_AXIS` / `CHART_GRID` directly (their canvas is
  outside the CSS-var cascade, so they do **not** flip with dark mode — the
  neutrals are mid-tone on purpose).
- **No webfont.** `--admin-font` is a system stack with Hangul fallbacks for
  platforms whose UI font has no Hangul coverage (`Segoe UI` does not, so Windows
  falls through to Malgun Gothic). #193's self-hosted Wanted Sans and the
  `/admin-static` mount that served it are gone. The emitted CSS contains no
  `@font-face` and no `url(` at all, pinned by
  `test_font_is_a_system_stack_with_no_webfont` — so the panel makes no
  third-party request on load. A fork adding a webfont must restore the static
  mount in `_apps/admin/bootstrap.py` and relax that test.
- **`--admin-drawer-text` must differ from `--admin-text-muted`.** `layout.py`
  mutes inactive nav icons with `.admin-text-muted`, and `.admin-nav-section`
  colours section headers from the same token; equal values make both a silent
  no-op. Pinned by `test_drawer_text_and_muted_are_distinct_in_both_modes`.
- **AG Grid surfaces come from `--admin-*`, all of them or none.** `.admin-grid`
  maps `--ag-background-color`, `--ag-header-background-color`,
  `--ag-border-color`, `--ag-row-border`, `--ag-row-hover-color` and
  `--ag-odd-row-background-color` onto the theme tokens. Setting only *some* is
  the trap: pinning the odd row to kill striping while the grid body keeps the
  quartz surface makes striping reappear **inverted**. Zebra striping is off by
  design (`--admin-row-alt` == `--admin-surface`) — rows separate by border.
  `--ag-row-border` is the v33 Theming API name; the legacy
  `--ag-row-border-{color,style,width}` trio no longer applies.
- **State transitions, not motion.** `_HELPER_CSS` eases colour and border
  changes on cards, buttons, nav items, grid rows and inputs — and nothing
  moves. There is no hover-lift and no press-squish (both were removed in #365
  as dated on a data-dense admin surface); `test_no_lift_on_hover` fails on any
  `transform` declaration in the payload. Everything is disabled under
  `prefers-reduced-motion`. Don't re-implement hover/press feedback per page.
- **Single focused flow (page-author convention).** A page shows what the user
  must do *now* — current step, progress, and the stop/cancel action — before
  anything secondary. Guided flows (e.g. `/admin/setup`) read top-to-bottom as
  one task, not a dense form grid.
- **Single primary CTA (page-author convention).** At most one `color=primary`
  button per view; supporting actions stay flat/secondary, destructive ones use
  `c.confirm_dialog`. The primary button is the one thing the focused flow is
  driving toward.

> **AG Grid rendering fix (gotcha).** AG Grid v33 hides cells via
> `:where(.ag-delay-render) … { visibility:hidden }` until first render, then
> drops the class. In the NiceGUI embed the class can get stuck (grid initialises
> before its container is laid out), leaving rows permanently invisible — data is
> in the DOM but the grid looks empty. `_HELPER_CSS` forces
> `.admin-grid .ag-cell/.ag-row/.ag-header-cell` to `visibility: visible`
> (the zero-specificity `:where()` rule cannot win). Keep this when touching grid CSS.

## Component catalog

Import surface: `from src._core.infrastructure.admin import components as c`.

| Builder | Kind | Use |
|---------|------|-----|
| `c.page_header(title, *, subtitle=, back_to=, actions=)` | leaf | Page heading; `back_to` adds a back button, `actions` a right-aligned slot |
| `c.card(*, clickable_to=, classes=)` | context mgr | A themed card; `clickable_to` makes the whole card navigate |
| `c.section(title=)` | context mgr | A titled content section |
| `c.stat_card(label, value, *, icon=)` | leaf | Metric tile (caption + value) |
| `c.field_row(label, value, *, is_empty=)` | leaf | One label/value detail row (value pre-formatted) |
| `c.text_field / textarea_field / number_field / select_field` | leaf | Form inputs — always `outlined` |
| `c.action_dialog(title, *, width=, subtitle=)` | context mgr | Dialog with arbitrary body; yields `(dialog, card)`; opens on exit |
| `c.confirm_dialog(title, message, *, on_confirm, on_success=, danger=)` | async | Confirm-an-action; see contract below |
| `c.data_grid(column_defs, row_data, *, compact=, auto_height=, row_click_to=, on_cell_click=, on_row_click=)` | leaf | AG Grid with the admin theme + shared defaults. Height: default = viewport-sized, `compact=True` = shorter, `auto_height=True` = derived from the row count (no empty space under the last row) — only for a **caller-bounded** row count. `auto_height` deliberately avoids AG Grid's `domLayout: "autoHeight"`, which breaks in the NiceGUI embed: the inner wrapper grows past the outer element and paints over the next section |
| `c.bar_chart(categories, values)` | leaf | ECharts vertical bar; sized by `AdminClasses.CHART` / `--admin-chart-height`, bar fill = `AdminColors.PRIMARY`, top corners rounded |
| `c.pagination(*, current, total_pages, on_prev, on_next)` | leaf | Prev / page / next row |
| `c.empty_state(icon=)` | context mgr | Centered empty placeholder; add the message inside |
| `c.toast_success / toast_warning / toast_error(message)` | leaf | Standardized `ui.notify` |
| `c.report_error(exc, *, context)` | async | Route a caught exception through the sanitizing `AdminErrorHandler` |

### `confirm_dialog` contract (important)

`on_confirm()` does the work, owns its own try/except + audit + notifications,
and **returns `success: bool`**. The builder owns only the loading state and
ordering: it wraps `on_confirm` in `button_loading`, and **only on `True`**
closes the dialog and then awaits `on_success` (e.g. a list refresh). On
`False` the dialog stays open. Never close / navigate from inside `on_confirm`.

## Recipe: build a new admin page

1. **Standard CRUD** → just a `BaseAdminPage` config (no custom rendering). The
   base class already routes through the component builders, so you get the
   system for free. Use `/add-admin-page`.
2. **Custom page** (summary, dashboard widget, playground):
   - `require_auth*` is the **first statement** (enforced by
     `test_route_coverage.py`).
   - `@admin_error_boundary(context=...)` on the route.
   - `admin_layout(...)` for the shell, then compose `c.page_header`, `c.card` /
     `c.section`, `c.stat_card`, `c.data_grid`, … — never raw `ui.card` /
     `ui.aggrid` for these shapes.
3. **Write actions** → `c.confirm_dialog` (destructive) / `c.action_dialog`
   (forms). `on_confirm` owns audit + notify; the builder owns close/refresh.

## DO / DON'T

**DO**
- Use `c.text_field` (outlined enforced) and the other form builders.
- Use `c.confirm_dialog` for destructive actions.
- Surface caught exceptions via `c.report_error` (sanitized).
- Add a new shared shape as a builder in `components/`, not an inline page helper.

**DON'T**
- Hardcode `bg-*` / `text-*` / `border-*` palette classes or inline `height: Npx`
  on a grid (the AST guard fails).
- Call `ui.notify(str(exc))` / `c.toast_error(str(exc))` — leaks internals.
- Put `require_auth` anywhere but the first statement of the route.
- Add a builder that wraps a single `ui.label` with no shared behavior.

## Reference

- Tokens: `src/_core/infrastructure/admin/theme.py`
- Builders: `src/_core/infrastructure/admin/components/`
- Base page: `src/_core/infrastructure/admin/base_admin_page.py`
- Guards: `tests/unit/_core/infrastructure/admin/test_no_hardcoded_styles.py`,
  `test_route_coverage.py`
- Admin page DI pattern: `docs/ai/shared/project-dna.md` §11
