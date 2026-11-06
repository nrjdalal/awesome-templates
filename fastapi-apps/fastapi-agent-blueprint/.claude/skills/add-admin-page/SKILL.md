---
name: add-admin-page
argument-hint: domain_name
description: |
  This skill should be used when the user asks to
  "add admin page", "add admin", "admin dashboard",
  or wants to add NiceGUI admin pages to an existing domain.
---

# Add Admin Page to Existing Domain

Input: $ARGUMENTS

## Default Flow Position
See [target-operating-model §1](../../../docs/ai/shared/target-operating-model.md) — `add-admin-page` routing.

## Procedure Authority
Read and follow the [full procedure](../../../docs/ai/shared/skills/add-admin-page.md) before acting; it owns requirements, gates and outputs.

## Procedure Overview
1. Analysis — verify domain exists, read DTO fields, ask user preferences
2. Implementation — directory structure → admin config → page routes
3. Verification — pre-commit, import check, server start
