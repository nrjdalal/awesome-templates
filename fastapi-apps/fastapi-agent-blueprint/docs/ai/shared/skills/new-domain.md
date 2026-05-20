# New Domain Scaffolding — Detailed Procedure

## Default Flow Position

This skill participates in the [Default Coding Flow](../../../../AGENTS.md#default-coding-flow) at the **`implement`** step.

Because creating a new domain is an architecture commitment (new boundary, optional AI infra decision, cross-domain integration surface), the **`approach options`** step is mandatory before invoking this skill. Run `/plan-feature` first to settle the domain boundary, key fields, and Optional AI Infra Variant.

After implementation, route to:
- `verify` — `/test-domain {name} run` (or `pytest tests/unit/{name}/ -v`)
- `self-review` — `/review-architecture {name}`
- `completion gate` — `/sync-guidelines` if shared docs reference the new domain

## Pre-check
1. Verify domain name is a valid Python identifier (lowercase, underscores allowed, hyphens prohibited)
2. Verify `src/{name}/` directory does not already exist — abort if it does
3. Ask the user about the domain's **key fields** (e.g., name, description, price, etc.)

## Scaffolding Procedure

Use `src/user/` as the Reference and create 6 Layers in order.
Read the corresponding user file before creating each file and replicate the pattern.

Refer to `docs/ai/shared/scaffolding-layers.md` for the detailed file list and import paths.

**Layer order**: Domain -> Application -> Infrastructure -> Interface -> App Wiring -> Tests

Default 44 files (15 content + 25 `__init__.py` + 4 tests), with UseCase 46 files.

## Architecture Rules
Follow the shared rules in `AGENTS.md`, especially "Absolute Prohibitions" and "Conversion Patterns".

## Verification after Completion
1. `python -c "from src.{name}.domain.dtos.{name}_dto import {Name}DTO; print('OK')"` — verify import
2. Run pre-commit: `pre-commit run --files src/{name}/**/*.py`
3. Run tests: `pytest tests/unit/{name}/ -v`
4. Report results to the user
