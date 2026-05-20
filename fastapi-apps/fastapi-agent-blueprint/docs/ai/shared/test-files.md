# Required Test Files

> Canonical definition of test files required per domain.
> Consumed by `/test-domain`, `/review-architecture`, `/new-domain`, and planning references.
> All other documents referencing required test files must point here rather than maintaining their own list.

## Baseline (always required)

These three files are required for every persistence-backed domain:

- `tests/factories/{name}_factory.py`
- `tests/unit/{name}/domain/test_{name}_service.py`
- `tests/integration/{name}/infrastructure/test_{name}_repository.py`

For non-persistence AI domains that intentionally have no Repository
(`BaseRepository` / `BaseDynamoRepository` subclass), replace the repository
integration baseline with equivalent integration coverage for the domain's
Protocol + Adapter + Selector behavior, for example
`tests/integration/{name}/test_{name}_stub_fallback.py`.

## Conditional (required when the feature exists)

| File | Condition |
|---|---|
| `tests/unit/{name}/application/test_{name}_use_case.py` | UseCase exists in the domain |
| `tests/e2e/{name}/test_{name}_router.py` | Server router / API exists |
| `tests/unit/{name}/interface/admin/test_{name}_admin_config.py` | Admin interface exists |

## Usage by Skill

- `/test-domain generate` — generates all missing baseline files plus applicable conditionals
- `/review-architecture §5` — checks for baseline files; conditionals checked when the corresponding feature exists
- `/new-domain` scaffolding — creates baseline + applicable conditionals at domain creation time
