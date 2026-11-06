# Cross-Domain Dependency Wiring — Detailed Procedure

## Default Flow Position
See [target-operating-model §1](../target-operating-model.md) — `add-cross-domain` routing.

## Analysis

1. Identify the consumer domain and the provider domain
2. Determine what functionality the consumer needs from the provider
3. Explore the current structure of both domains

## Core Rules
- The consumer's Service depends only on the provider's **Protocol** (direct import of implementation is prohibited)
- Protocols are located in the provider's `domain/protocols/` (dependency between domain layers is allowed)
- Actual implementation wiring is performed only in the DI Container
- Absolute Prohibitions: importing from the provider's `infrastructure/` in the consumer's `domain/` folder
- DI Container pattern: see `docs/ai/shared/project-dna.md` §5
- Base class import paths: see `docs/ai/shared/project-dna.md` §2

## Implementation Order

### 1. Verify Provider Protocol
In `src/{provider}/domain/protocols/{provider}_repository_protocol.py`:
- Check if the methods the consumer needs already exist
- If not, add methods to Protocol → add implementation to Repository

### 2. Modify Consumer Service
In `src/{consumer}/domain/services/{consumer}_service.py`:
```python
from src.{provider}.domain.protocols.{provider}_repository_protocol import {Provider}RepositoryProtocol

class {Consumer}Service:
    def __init__(
        self,
        {consumer}_repository: {Consumer}RepositoryProtocol,
        {provider}_repository: {Provider}RepositoryProtocol,  # added
    ) -> None:
        self.{consumer}_repository = {consumer}_repository
        self.{provider}_repository = {provider}_repository  # added
```

### 3. Modify Consumer DI Container
In `src/{consumer}/infrastructure/di/{consumer}_container.py`:
```python
from src.{provider}.infrastructure.repositories.{provider}_repository import {Provider}Repository

class {Consumer}Container(containers.DeclarativeContainer):
    core_container = providers.DependenciesContainer()

    # Provider repository (external domain)
    {provider}_repository = providers.Singleton(
        {Provider}Repository,
        database=core_container.database,
    )

    {consumer}_repository = providers.Singleton(...)

    {consumer}_service = providers.Factory(
        {Consumer}Service,
        {consumer}_repository={consumer}_repository,
        {provider}_repository={provider}_repository,  # wired
    )
```

### 4. Verify App DI Container
In `src/_apps/server/di/container.py`:
- Verify that both domains are registered
- Wire cross-container dependencies if needed

## Anti-patterns (Absolute Prohibitions)
- Directly importing provider Service in consumer Service (inter-Service dependency is prohibited)
- Importing provider infrastructure from consumer domain
- Creating a "common" service class — resolve via Protocol dependency instead
- Creating separate Mapper or Adapter classes

## Verification
1. Use Grep to confirm there are no provider `infrastructure` imports in the consumer's `domain/` folder
2. Run tests for both domains:
   ```bash
   pytest tests/unit/{consumer}/ tests/unit/{provider}/ -v
   ```
3. Run pre-commit
