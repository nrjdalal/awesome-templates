# Architecture Audit Checklist Details

> Refer to `docs/ai/shared/project-dna.md` for expected patterns.
> This checklist defines architecture findings for `/review-architecture` and
> `/review-pr`.
>
> Taxonomy:
> - Rule type: every item below is a `code-auditable rule`
> - Review state is assigned by the review procedure: `OPEN`, `OK`, `SKIP`
> - Severity is declared here: `BLOCKING`, `HIGH`, `MEDIUM`, `LOW`, `NOTE`
>
> The shared-rule-source cross-reference safeguard remains in `AGENTS.md` and
> harness docs because it is a process rule, not a code-grep rule.

## 1. Layer Dependency Rules

Grep-check Python files in each domain.

- [ ] [BLOCKING] No `from src.{name}.infrastructure` imports in `src/{name}/domain/` files
- [ ] [BLOCKING] No `from src.{name}.interface` imports in `src/{name}/domain/` files, except `schemas/`
- [ ] [BLOCKING] No `from src.{name}.infrastructure` imports in `src/{name}/application/` files, excluding DI-only wiring
- [ ] [BLOCKING] No `from sqlalchemy` imports in `src/{name}/domain/` files
- [ ] [HIGH] No `from dependency_injector` imports in `src/{name}/domain/` files

## 2. Conversion Patterns Compliance

Check across all domain files.

- [ ] [BLOCKING] No `class.*Mapper` class definitions
- [ ] [BLOCKING] No Entity pattern remnants (`to_entity(`, `from_entity(`, `Entity` class definitions)
- [ ] [BLOCKING] Persistence models (`Model`, `DynamoModel`, `VectorModel`) are not imported or exposed outside Repository / VectorStore layers
- [ ] [BLOCKING] Repository method return values are DTO types, not Model objects
- [ ] [HIGH] Model -> DTO conversion uses `model_validate(..., from_attributes=True)`
- [ ] [HIGH] Persistence service classes use 3 TypeVars: `BaseService[Create{Name}Request, Update{Name}Request, {Name}DTO]` or `BaseDynamoService[Create{Name}Request, Update{Name}Request, {Name}DTO]`; Protocol-delegating AI services that do not extend a base CRUD service are exempt.
- [ ] [HIGH] Service method overrides match parent signature types and do not narrow parameters

## 3. DTO / Response Integrity

Check `interface/server/schemas/` files.

- [ ] [HIGH] Response classes inherit only from `BaseResponse`
- [ ] [HIGH] Request classes inherit only from `BaseRequest`
- [ ] [BLOCKING] Sensitive fields are not included in Response classes
- [ ] [HIGH] Routers use `model_dump(exclude={...})` when a DTO contains sensitive data

## 4. DI Container Correctness

Check `infrastructure/di/` files and compare with `project-dna` section 5.

- [ ] [HIGH] Container inherits from `containers.DeclarativeContainer`
- [ ] [HIGH] `core_container = providers.DependenciesContainer()` is declared
- [ ] [HIGH] Repository providers use `providers.Singleton`
- [ ] [HIGH] Service providers use `providers.Factory`
- [ ] [MEDIUM] UseCase providers use `providers.Factory`

## 5. Test Coverage

Check required test paths for the audited domain.
See `docs/ai/shared/test-files.md` for the canonical baseline and conditional file definitions.

- [ ] [MEDIUM] All baseline test files exist (factories, domain service unit, repository integration — or Protocol + Adapter + Selector integration coverage for non-persistence AI domains; see `docs/ai/shared/test-files.md` for canonical definitions)
- [ ] [MEDIUM] Applicable conditional test files exist (use_case unit when UseCase present, e2e router when API present, admin_config when admin present)

## 6. Worker Payload Compliance

Check `interface/worker/` files.

- [ ] [HIGH] Worker tasks validate `**kwargs` via a Payload class, not directly via a domain DTO
- [ ] [HIGH] Payload classes inherit from `BasePayload`, not `BaseModel` or `BaseRequest`
- [ ] [MEDIUM] Payload files live in `interface/worker/payloads/`, not the domain layer
- [ ] [LOW] When fields match, the Payload is passed directly to the Service
- [ ] [MEDIUM] When fields differ, the task performs explicit DTO conversion

## 7. Admin Page Compliance

Check `interface/admin/` files and compare with `project-dna` section 11.

- [ ] [MEDIUM] Config file exists at `src/{name}/interface/admin/configs/{name}_admin_config.py`
- [ ] [MEDIUM] Config variable is named `{name}_admin_page`
- [ ] [MEDIUM] Page file exists at `src/{name}/interface/admin/pages/{name}_page.py`
- [ ] [MEDIUM] Page file imports config from the configs module instead of defining it inline
- [ ] [HIGH] Page files do not import domain services directly
- [ ] [MEDIUM] `page_configs: list[BaseAdminPage] = []` is declared at module level
- [ ] Admin endpoint access restriction enforced — see security-checklist.md §2 for canonical rule and severity
- [ ] [HIGH] Sensitive fields use `masked=True` in `ColumnConfig`

## 8. Bootstrap Wiring

Check app-level files and auto-discovery wiring.

- [ ] [MEDIUM] `src/{name}/interface/server/bootstrap/{name}_bootstrap.py` exists
- [ ] [MEDIUM] `src/{name}/infrastructure/di/{name}_container.py` exists
- [ ] [MEDIUM] `src/{name}/__init__.py` exists
- [ ] [HIGH] `wire(packages=[...])` targets the correct packages
- [ ] [NOTE] Domain discovery is automatic; manual app-level registration should not be added unless the pattern itself changes

## 9. DynamoDB Domain Compliance

Check only when a domain uses DynamoDB (`infrastructure/dynamodb/` exists).

- [ ] [HIGH] DynamoDB models live in `infrastructure/dynamodb/models/`
- [ ] [HIGH] DynamoDB models inherit from `DynamoModel`, not SQLAlchemy `Base`
- [ ] [HIGH] Repository inherits from `BaseDynamoRepository[{Name}DTO]`, not `BaseRepository`
- [ ] [HIGH] Service inherits from `BaseDynamoService[Create{Name}Request, Update{Name}Request, {Name}DTO]`, not `BaseService`
- [ ] [HIGH] DI container uses `dynamodb_client=core_container.dynamodb_client`, not `database=core_container.database`
- [ ] [BLOCKING] No `from sqlalchemy` imports remain in DynamoDB domain files
- [ ] [HIGH] Protocol inherits from `BaseDynamoRepositoryProtocol[{Name}DTO]`, not `BaseRepositoryProtocol`
