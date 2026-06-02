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
   ▲ consumed by    + build_admin_css() presets + Wanted Sans font
components/         builders — the ONLY place tokens become elements
   ▲ consumed by
base_admin_page.py  layout.py        interface/admin + _apps/admin pages
```

The dependency is one-directional: `components/` consumes `theme.py`; pages and
`BaseAdminPage` consume `components/`. **Components must never import
`base_admin_page`** (cycle). Value formatting / masking / column selection stay
in the caller; builders only render what they are given.

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
| `c.data_grid(column_defs, row_data, *, compact=, row_click_to=, on_cell_click=, on_row_click=)` | leaf | AG Grid with the admin theme + shared defaults |
| `c.bar_chart(categories, values)` | leaf | ECharts vertical bar; sized by `AdminClasses.CHART` / `--admin-chart-height`, bar fill tracks the active `ADMIN_THEME_PALETTE` accent |
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
