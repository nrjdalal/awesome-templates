# Add API Endpoint — Detailed Procedure

## Default Flow Position

This skill participates in the [Default Coding Flow](../../../../AGENTS.md#default-coding-flow) at the **`implement`** step.

`approach options` upstream is **conditionally mandatory**: required when the new endpoint introduces non-trivial response shape, cross-domain access, or a new validation pattern. Skip when the endpoint is a straightforward CRUD addition with existing DTOs.

After implementation, route to:
- `verify` — `/test-domain {name} run`
- `self-review` — `/review-architecture {name}` only if you introduced new layer interactions
- `completion gate` — `/sync-guidelines` if shared docs reference the new endpoint

## Analysis

1. Identify from the request: domain name, HTTP method, path, purpose
2. Explore the domain's existing Router, Service, Repository (also check UseCase if present)
3. Determine what is needed:
   - Is a new Request/Response DTO required? (Or are existing ones sufficient?)
   - Is a new Service method required? (Or are BaseService methods sufficient?)
   - Is a new Repository method required? (Is a custom query needed?)
   - Is a UseCase required? (Only when complex logic such as combining multiple Services is involved)

## Implementation Order (Bottom-up)

### 1. Repository (only when a custom query is needed)
- Add method signature to Protocol: `src/{name}/domain/protocols/{name}_repository_protocol.py`
- Add implementation to Repository: `src/{name}/infrastructure/repositories/{name}_repository.py`
- Skip this step if BaseRepository methods are sufficient

### 2. Service
- Add method to `src/{name}/domain/services/{name}_service.py`
- BaseService provides basic CRUD + pagination, so only add methods when custom logic is needed

### 3. UseCase (only when complex logic is needed)
- Only add `src/{name}/application/use_cases/{name}_use_case.py` when a complex workflow such as combining multiple Services is required
- Simple CRUD is sufficient with direct Router → Service injection

### 4. Interface DTO (if needed)
- Add Request/Response to `src/{name}/interface/server/schemas/{name}_schema.py`
- Request inherits from `BaseRequest`, Response inherits from `BaseResponse`
- **Explicit field declaration** (single inheritance from BaseRequest/BaseResponse only)

### 5. Router
- Add endpoint to `src/{name}/interface/server/routers/{name}_router.py`
- Router pattern: see `docs/ai/shared/project-dna.md` §9
- Conversion Patterns: see `docs/ai/shared/project-dna.md` §6

## Conversion Rules
For Conversion Patterns see `docs/ai/shared/project-dna.md` §6. For import paths see `docs/ai/shared/project-dna.md` §2.

## Post-completion Verification
1. Run pre-commit
2. Add tests for the new method to the domain's unit tests
3. Inform that the endpoint can be verified in Swagger after starting the server
