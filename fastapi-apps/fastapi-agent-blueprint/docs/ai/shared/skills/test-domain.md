# Domain Test Generation/Execution — Detailed Procedure

## Default Flow Position

This skill is the canonical owner of the **`verify`** step in the [Default Coding Flow](../../../../AGENTS.md#default-coding-flow).

- `run` mode is the standard verification action after any `implement` step.
- `generate` mode prepares the test surface and is itself an `implement`-style operation; the resulting tests must then be exercised via `run`.

After verification, route to:
- `self-review` — `/review-architecture {name}` if the change introduced layer interactions
- `completion gate` — `/review-pr` and (if drift) `/sync-guidelines`

Recursion guard: n/a (this skill is the verify step, not a planning step).

## Mode Selection

If the argument contains "generate", generate missing test files.
If the argument contains "run", execute existing tests.
If neither is present, ask the user which mode they want.

## Required Test Files

See `docs/ai/shared/test-files.md` for the canonical baseline and conditional file definitions.

Refer to `docs/ai/shared/test-patterns.md` for detailed test patterns and Factory code examples.

## Generate Mode Procedure
1. Read `src/{name}/` to identify all Service/UseCase methods
2. Check existing test files in `tests/` directory
3. Generate missing files (the 4 above + necessary `__init__.py`)

## Run Mode Procedure
```bash
# Unit tests
pytest tests/unit/{name}/ -v

# Integration tests
pytest tests/integration/{name}/ -v

# All
pytest tests/unit/{name}/ tests/integration/{name}/ tests/e2e/{name}/ -v
```

If any tests fail, analyze the cause and suggest fixes.

## Verification After Generation
1. Verify generated test file imports: `python -c "from tests.unit.{name}.domain.test_{name}_service import *; print('OK')"`
2. Run tests: `pytest tests/unit/{name}/ tests/integration/{name}/ -v`
3. Run pre-commit: `pre-commit run --files tests/**/{name}/**/*.py`
