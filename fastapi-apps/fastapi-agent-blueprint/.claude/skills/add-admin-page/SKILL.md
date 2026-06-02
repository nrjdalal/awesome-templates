---
name: add-admin-page
argument-hint: domain_name
description: |
  This skill should be used when the user asks to
  "add admin page", "add admin", "admin dashboard",
  or wants to add NiceGUI admin pages to an existing domain.
---

# Add Admin Page to Existing Domain

Domain name: $ARGUMENTS

## Default Flow Position
- Step: `implement` (`approach options` upstream conditional — required for sensitive fields or new admin auth surfaces)
- Routes after: `/test-domain {name} run` (verify) → `/security-review` (self-review) if sensitive fields exposed
- Recursion guard: do not invoke `/plan-feature` from inside this skill

## Procedure Overview
1. Analysis — verify domain exists, read DTO fields, ask user preferences
2. Implementation — directory structure → admin config → page routes
3. Verification — pre-commit, import check, server start

## Core Rules
- CRUD pages are config-only `BaseAdminPage` instances — they inherit the design
  system automatically (the base class renders via the component builders).
- **Custom / non-CRUD pages MUST compose `admin.components` builders** (`c.page_header`,
  `c.card`, `c.stat_card`, `c.data_grid`, `c.confirm_dialog`, …) — never raw
  `ui.card` / `ui.aggrid` / `ui.dialog` for those shapes, and never hardcoded
  color classes or inline grid heights (AST-guarded).
- Every route: `@admin_error_boundary(...)` + `require_auth*` as the first statement.
- A new shared UI shape gets a builder in `components/`, not an inline page helper.

Read `docs/ai/shared/skills/add-admin-page.md` for detailed steps and code templates.
Refer to `docs/ai/shared/admin-design-system.md` for the component catalog + DO/DON'T,
and `docs/ai/shared/project-dna.md` §11 for the admin page DI pattern.
