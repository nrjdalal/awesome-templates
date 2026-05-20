---
name: add-admin-page
description: Add a NiceGUI admin page for an existing domain while keeping config and page routing separated and masking sensitive fields.
metadata:
  short-description: Add admin page
---

# Add Admin Page

## Default Flow Position
- Step: `implement` (`approach options` upstream conditional — required for sensitive fields or new admin auth surfaces)
- Routes after: verify (`/test-domain {name} run`) → self-review (`/security-review` if sensitive fields exposed)
- Recursion guard: do not invoke `/plan-feature` from inside this skill

## Procedure
1. Read `AGENTS.md` and `docs/ai/shared/skills/add-admin-page.md` for the full procedure.
2. Read `docs/ai/shared/project-dna.md` §11 for admin page pattern.
3. Inspect the target domain DTO and the reference admin under `src/user/interface/admin/`.
4. Create config file and page route file in separate directories.
5. Keep `BaseAdminPage` in config only; keep `@ui.page` in page only.
6. Mask sensitive fields and do not add manual bootstrap registration.
