# Test Pattern Details

## Test Pyramid

### Unit Tests — `tests/unit/{name}/`

#### Service Tests (`tests/unit/{name}/domain/test_{name}_service.py`)
- MockRepository class: implement all Protocol methods with in-memory dict
- Test items:
  - `test_create_data` — verify DTO returned after creation
  - `test_get_data_by_data_id` — verify retrieval by ID
  - `test_get_datas_with_count` — verify pagination data + count
  - `test_update_data_by_data_id` — verify changed DTO after update
  - `test_delete_data_by_data_id` — verify True returned after deletion

#### UseCase Tests (`tests/unit/{name}/application/test_{name}_use_case.py`)
- MockService class: implement Service methods with Mock
- Test items:
  - `test_create_data` — verify UseCase delegates to Service
  - `test_get_datas` — verify PaginationInfo is correctly generated
  - `test_get_data_by_data_id` — verify single item retrieval delegation

### DynamoDB Service Tests (`tests/unit/{name}/domain/test_{name}_service.py`)
- MockDynamoRepository class: implement all `BaseDynamoRepositoryProtocol` methods with in-memory dict
- Key storage uses `DynamoKey(partition_key, sort_key)` as dict key
- Test items:
  - `test_create_item` — verify DTO returned after put_item
  - `test_get_item` — verify retrieval by DynamoKey
  - `test_query_items` — verify CursorPage returned with correct count
  - `test_update_item` — verify changed DTO after update
  - `test_delete_item` — verify True returned after deletion
- Reference implementation: `tests/unit/_core/infrastructure/persistence/nosql/dynamodb/test_base_dynamo_repository.py`

### Integration Tests — `tests/integration/{name}/`

#### Repository Tests (`tests/integration/{name}/infrastructure/test_{name}_repository.py`)
- Uses `test_db` fixture from `conftest.py` (SQLite in-memory)
- Test actual DB operations: insert -> select -> update -> delete

### E2E Tests — `tests/e2e/{name}/`

#### Router Tests (`tests/e2e/{name}/test_{name}_router.py`)
- Test HTTP requests with TestClient
- Verify status codes, response structure, error responses

## Factory Pattern
`tests/factories/{name}_factory.py` reference pattern: `tests/factories/user_factory.py`

```python
from datetime import datetime

from src.{name}.domain.dtos.{name}_dto import {Name}DTO
from src.{name}.interface.server.schemas.{name}_schema import (
    Create{Name}Request,
    Update{Name}Request,
)
from src.{name}.interface.worker.payloads.{name}_payload import {Name}TestPayload

def make_{name}_dto(
    id: int = 1,
    # ... domain field defaults with explicit keyword args
    created_at: datetime | None = None,
    updated_at: datetime | None = None,
) -> {Name}DTO:
    now = datetime.now()
    return {Name}DTO(
        id=id,
        # ... fields
        created_at=created_at or now,
        updated_at=updated_at or now,
    )

def make_create_{name}_request(
    # ... creation field defaults with explicit keyword args
) -> Create{Name}Request:
    return Create{Name}Request(
        # ... fields
    )

def make_update_{name}_request(
    # ... all fields Optional (field: type | None = None)
) -> Update{Name}Request:
    return Update{Name}Request(
        # ... fields
    )

def make_{name}_test_payload(
    id: int = 1,
    # ... worker-relevant fields (exclude sensitive fields like password)
    created_at: datetime | None = None,
    updated_at: datetime | None = None,
) -> {Name}TestPayload:
    now = datetime.now()
    return {Name}TestPayload(
        id=id,
        # ... fields
        created_at=created_at or now,
        updated_at=updated_at or now,
    )
```

### Password Assertion Pattern

When the domain Service hashes passwords (via `hash_password`), test assertions must use `verify_password` instead of direct comparison:

```python
from src._core.common.security import verify_password

async def test_create_data_hashes_password(service):
    request = make_create_{name}_request(password="plain_text")
    result = await service.create_data(entity=request)
    assert verify_password("plain_text", result.password)
```

### Admin Config Tests — `tests/unit/{name}/interface/admin/test_{name}_admin_config.py`

> Only when `src/{name}/interface/admin/configs/{name}_admin_config.py` exists.
> Reference: `tests/unit/_core/infrastructure/admin/test_base_admin_page.py`

```python
from src.{name}.interface.admin.configs.{name}_admin_config import {name}_admin_page


def test_domain_name_matches():
    assert {name}_admin_page.domain_name == "{name}"


def test_visible_columns_excludes_hidden():
    visible = {name}_admin_page.get_visible_columns()
    for col in visible:
        assert not col.hidden


def test_sensitive_fields_masked():
    """Fields like password, secret, token must use masked=True."""
    sensitive_keywords = {"password", "secret", "token", "key"}
    for col in {name}_admin_page.columns:
        if any(kw in col.field_name.lower() for kw in sensitive_keywords):
            assert col.masked, f"{col.field_name} should be masked"


def test_searchable_fields_configured():
    assert len({name}_admin_page.searchable_fields) > 0
```
