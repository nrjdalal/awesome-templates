# New Domain Scaffolding — Detailed Procedure

## Default Flow Position
See [target-operating-model §1](../target-operating-model.md) — `new-domain` routing.

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
