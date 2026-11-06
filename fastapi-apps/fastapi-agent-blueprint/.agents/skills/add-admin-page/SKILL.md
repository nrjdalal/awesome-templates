---
name: add-admin-page
description: Add a NiceGUI admin page for an existing domain while keeping config and page routing separated and masking sensitive fields.
metadata:
  short-description: Add admin page
---

# Add Admin Page

## Default Flow Position
See [target-operating-model §1](../../../docs/ai/shared/target-operating-model.md) — `add-admin-page` routing.

## Procedure Authority
Read `AGENTS.md`. Read and follow the [full procedure](../../../docs/ai/shared/skills/add-admin-page.md) before acting; it owns requirements, gates and outputs.

## Procedure Overview
1. Analysis — verify domain exists, read DTO fields, ask user preferences
2. Implementation — directory structure → admin config → page routes
3. Verification — pre-commit, import check, server start
