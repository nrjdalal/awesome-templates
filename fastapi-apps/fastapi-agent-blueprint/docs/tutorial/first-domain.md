# Your first domain in 10 minutes

Build a working `order` domain (CRUD endpoints + a unit test) from scratch.
By the end you will have a REST API you can `curl`, backed by SQLite,
with the same DDD layering the rest of the blueprint uses.

Two parallel paths are given side-by-side. They produce the same
result — **the AI skills are a convenience, not a requirement**:

| Path | Who it's for | What you run |
|---|---|---|
| **A. Harness-assisted** | You use Claude Code or Codex CLI | 3 slash / dollar commands |
| **B. Manual** | No AI tooling, or you want to see the scaffolding explicitly | 9 Python files + 1 test |

Whichever path you pick, the verification in [step 4](#step-4--verify-it-works) is identical.

## Prerequisites

- Python `>=3.12.9` and [`uv`](https://docs.astral.sh/uv/) installed
- A clone of this repo with `make setup` already run (see [quickstart](../quickstart.md))
- Expected time: **10 minutes**. No Docker, no PostgreSQL, no cloud credentials.

If you have not run the quickstart yet:

```bash
git clone https://github.com/Mr-DooSun/fastapi-agent-blueprint.git
cd fastapi-agent-blueprint
make setup        # venv + deps via uv
```

---

## Step 1 — Start the blueprint in one terminal

```bash
make quickstart   # SQLite + InMemory broker, FastAPI on :8001
```

Leave that running. Every command below runs in a *second* terminal
from the repo root.

---

## Step 2 — Scaffold the `order` domain

### Path A — Harness-assisted

```text
/new-domain order        # Claude Code  (use $new-domain order in Codex CLI)
```

That one command generates 15 source files + 25 `__init__.py` files +
4 test skeletons under `src/order/` and `tests/*/order/`. Skip to
[Step 3](#step-3--describe-an-order) to fill in the schema.

### Path B — Manual

Create the directory skeleton:

```bash
mkdir -p src/order/domain/{dtos,protocols,services,exceptions}
mkdir -p src/order/infrastructure/{database/models,repositories,di}
mkdir -p src/order/interface/server/{schemas,routers,bootstrap}
mkdir -p tests/unit/order
```

Drop an empty `__init__.py` into **every** directory you just created,
plus `src/order/__init__.py` itself. (These are what `discover_domains()`
uses to find the domain at startup — see
[`src/_core/infrastructure/discovery.py`](../../src/_core/infrastructure/discovery.py).)

```bash
find src/order tests/unit/order -type d -exec touch {}/__init__.py \;
```

---

## Step 3 — Describe an order

An order has a product name, a quantity, and a unit price. Four files
define that shape across three DDD layers — Domain, Interface, and
Infrastructure. A fifth file wires the three together via DI.

### 3.1 Domain — DTO, Protocol, Service

`src/order/domain/dtos/order_dto.py`

```python
from datetime import datetime

from pydantic import BaseModel, Field


class OrderDTO(BaseModel):
    id: int = Field(..., description="Order unique identifier")
    product_name: str = Field(..., description="Product name")
    quantity: int = Field(..., description="Quantity ordered")
    unit_price: int = Field(..., description="Unit price (minor units)")
    created_at: datetime = Field(..., description="Created at")
    updated_at: datetime = Field(..., description="Updated at")
```

`src/order/domain/protocols/order_repository_protocol.py`

```python
from src._core.domain.protocols.repository_protocol import BaseRepositoryProtocol
from src.order.domain.dtos.order_dto import OrderDTO


class OrderRepositoryProtocol(BaseRepositoryProtocol[OrderDTO]):
    pass
```

`src/order/domain/services/order_service.py`

```python
from src._core.domain.services.base_service import BaseService
from src.order.domain.dtos.order_dto import OrderDTO
from src.order.domain.protocols.order_repository_protocol import (
    OrderRepositoryProtocol,
)
from src.order.interface.server.schemas.order_schema import (
    CreateOrderRequest,
    UpdateOrderRequest,
)


class OrderService(BaseService[CreateOrderRequest, UpdateOrderRequest, OrderDTO]):
    def __init__(self, order_repository: OrderRepositoryProtocol) -> None:
        super().__init__(repository=order_repository)
```

Inheriting `BaseService[Create, Update, DTO]` is what gives you 7 async
CRUD methods (`create_data`, `get_data_by_data_id`, `get_datas`,
`update_data_by_data_id`, `delete_data_by_data_id`, …) for free.

### 3.2 Interface — Request / Response schemas

`src/order/interface/server/schemas/order_schema.py`

```python
from datetime import datetime

from pydantic import Field

from src._core.application.dtos.base_request import BaseRequest
from src._core.application.dtos.base_response import BaseResponse


class OrderResponse(BaseResponse):
    id: int
    product_name: str
    quantity: int
    unit_price: int
    created_at: datetime
    updated_at: datetime


class CreateOrderRequest(BaseRequest):
    product_name: str = Field(max_length=255)
    quantity: int = Field(ge=1)
    unit_price: int = Field(ge=0)


class UpdateOrderRequest(BaseRequest):
    product_name: str | None = Field(default=None, max_length=255)
    quantity: int | None = Field(default=None, ge=1)
    unit_price: int | None = Field(default=None, ge=0)
```

### 3.3 Infrastructure — ORM model + Repository

`src/order/infrastructure/database/models/order_model.py`

```python
from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from src._core.infrastructure.persistence.rdb.database import Base


class OrderModel(Base):
    __tablename__ = "order"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_name: Mapped[str] = mapped_column(String(255), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[DateTime] = mapped_column(
        DateTime, server_default=func.now(), nullable=True
    )
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=True
    )
```

`src/order/infrastructure/repositories/order_repository.py`

```python
from src._core.infrastructure.persistence.rdb.base_repository import BaseRepository
from src._core.infrastructure.persistence.rdb.database import Database
from src.order.domain.dtos.order_dto import OrderDTO
from src.order.infrastructure.database.models.order_model import OrderModel


class OrderRepository(BaseRepository[OrderDTO]):
    def __init__(self, database: Database) -> None:
        super().__init__(
            database=database,
            model=OrderModel,
            return_entity=OrderDTO,
        )
```

### 3.4 DI Container — wire service to repository

`src/order/infrastructure/di/order_container.py`

```python
from dependency_injector import containers, providers

from src.order.domain.services.order_service import OrderService
from src.order.infrastructure.repositories.order_repository import OrderRepository


class OrderContainer(containers.DeclarativeContainer):
    core_container = providers.DependenciesContainer()

    order_repository = providers.Singleton(
        OrderRepository,
        database=core_container.database,
    )

    order_service = providers.Factory(
        OrderService,
        order_repository=order_repository,
    )
```

### 3.5 Interface — Router + domain bootstrap

`src/order/interface/server/routers/order_router.py`

```python
from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, Query

from src._core.application.dtos.base_response import SuccessResponse
from src.order.domain.services.order_service import OrderService
from src.order.infrastructure.di.order_container import OrderContainer
from src.order.interface.server.schemas.order_schema import (
    CreateOrderRequest,
    OrderResponse,
    UpdateOrderRequest,
)

router = APIRouter()


@router.post(
    "/order",
    summary="Create order",
    response_model=SuccessResponse[OrderResponse],
    response_model_exclude={"pagination"},
)
@inject
async def create_order(
    item: CreateOrderRequest,
    order_service: OrderService = Depends(Provide[OrderContainer.order_service]),
) -> SuccessResponse[OrderResponse]:
    data = await order_service.create_data(entity=item)
    return SuccessResponse(data=OrderResponse(**data.model_dump()))


@router.get(
    "/orders",
    summary="List orders",
    response_model=SuccessResponse[list[OrderResponse]],
)
@inject
async def list_orders(
    page: int = 1,
    page_size: int = Query(10, alias="pageSize"),
    order_service: OrderService = Depends(Provide[OrderContainer.order_service]),
) -> SuccessResponse[list[OrderResponse]]:
    datas, pagination = await order_service.get_datas(page=page, page_size=page_size)
    return SuccessResponse(
        data=[OrderResponse(**d.model_dump()) for d in datas],
        pagination=pagination,
    )


@router.get(
    "/order/{order_id}",
    summary="Get order by ID",
    response_model=SuccessResponse[OrderResponse],
    response_model_exclude={"pagination"},
)
@inject
async def get_order_by_id(
    order_id: int,
    order_service: OrderService = Depends(Provide[OrderContainer.order_service]),
) -> SuccessResponse[OrderResponse]:
    data = await order_service.get_data_by_data_id(data_id=order_id)
    return SuccessResponse(data=OrderResponse(**data.model_dump()))


@router.put(
    "/order/{order_id}",
    summary="Update order",
    response_model=SuccessResponse[OrderResponse],
    response_model_exclude={"pagination"},
)
@inject
async def update_order_by_id(
    order_id: int,
    item: UpdateOrderRequest,
    order_service: OrderService = Depends(Provide[OrderContainer.order_service]),
) -> SuccessResponse[OrderResponse]:
    data = await order_service.update_data_by_data_id(data_id=order_id, entity=item)
    return SuccessResponse(data=OrderResponse(**data.model_dump()))


@router.delete(
    "/order/{order_id}",
    summary="Delete order",
    response_model=SuccessResponse,
    response_model_exclude={"data", "pagination"},
)
@inject
async def delete_order_by_id(
    order_id: int,
    order_service: OrderService = Depends(Provide[OrderContainer.order_service]),
) -> SuccessResponse:
    success = await order_service.delete_data_by_data_id(data_id=order_id)
    return SuccessResponse(success=success)
```

`src/order/interface/server/bootstrap/order_bootstrap.py`

```python
"""Order domain independent bootstrap"""

from fastapi import FastAPI

from src._core.infrastructure.persistence.rdb.database import Database
from src.order.infrastructure.di.order_container import OrderContainer
from src.order.interface.server.routers import order_router


def create_order_container(order_container: OrderContainer):
    order_container.wire(packages=["src.order.interface.server.routers"])
    return order_container


def setup_order_routes(app: FastAPI):
    app.include_router(router=order_router.router, prefix="/v1", tags=["Order"])


def bootstrap_order_domain(
    app: FastAPI, database: Database, order_container: OrderContainer
):
    order_container = create_order_container(order_container=order_container)
    setup_order_routes(app=app)
```

---

## Step 4 — Verify it works

Stop the running server (Ctrl+C in the first terminal), then restart it
to re-create the SQLite schema with the new `order` table:

```bash
rm -f ./quickstart.db && make quickstart
```

> The `order` table is auto-created at boot in `ENV=quickstart` mode
> (see [`src/_apps/server/bootstrap.py`](../../src/_apps/server/bootstrap.py)).
> Real environments use Alembic — see
> [`migrate-domain`](../ai-development.md) skill or
> `alembic revision --autogenerate`.

Exercise the new endpoints:

```bash
curl -sS -X POST http://127.0.0.1:8001/v1/order \
  -H 'Content-Type: application/json' \
  -d '{"productName":"Mechanical keyboard","quantity":2,"unitPrice":12900}'
```

```json
{
  "success": true,
  "message": "Request processed successfully",
  "data": {
    "id": 1,
    "productName": "Mechanical keyboard",
    "quantity": 2,
    "unitPrice": 12900,
    "createdAt": "...",
    "updatedAt": "..."
  }
}
```

```bash
curl -sS http://127.0.0.1:8001/v1/orders?page=1\&pageSize=10
curl -sS -X PUT http://127.0.0.1:8001/v1/order/1 \
  -H 'Content-Type: application/json' -d '{"quantity":3}'
curl -sS -X DELETE http://127.0.0.1:8001/v1/order/1
```

Open <http://127.0.0.1:8001/docs> (pick Swagger from the selector) — the `Order` tag is now
listed alongside `User`. **No edits were needed in `src/_apps/`**:
domain auto-discovery picked the new folder up.

---

## Step 5 — Add a unit test

### Path A

```text
/test-domain order generate
```

### Path B

Tests in this repo use a **protocol-based mock** — you don't inherit
the real repository, you just implement the methods the service calls.

`tests/unit/order/test_order_service.py`

```python
from datetime import datetime

import pytest
from pydantic import BaseModel

from src.order.domain.dtos.order_dto import OrderDTO
from src.order.domain.services.order_service import OrderService
from src.order.interface.server.schemas.order_schema import (
    CreateOrderRequest,
    UpdateOrderRequest,
)


class MockOrderRepository:
    def __init__(self):
        self._store: dict[int, OrderDTO] = {}
        self._next_id = 1

    async def insert_data(self, entity: BaseModel) -> OrderDTO:
        now = datetime.now()
        dto = OrderDTO(
            id=self._next_id, created_at=now, updated_at=now, **entity.model_dump()
        )
        self._store[self._next_id] = dto
        self._next_id += 1
        return dto

    async def select_data_by_id(self, data_id: int) -> OrderDTO:
        return self._store[data_id]

    async def select_datas_with_count(self, page, page_size, query_filter=None):
        items = list(self._store.values())
        start = (page - 1) * page_size
        return items[start : start + page_size], len(items)

    async def update_data_by_data_id(self, data_id: int, entity: BaseModel) -> OrderDTO:
        dto = self._store[data_id]
        updated = dto.model_copy(
            update={k: v for k, v in entity.model_dump().items() if v is not None}
        )
        self._store[data_id] = updated
        return updated

    async def delete_data_by_data_id(self, data_id: int) -> bool:
        self._store.pop(data_id, None)
        return True

    async def count_datas(self) -> int:
        return len(self._store)


@pytest.fixture
def order_service():
    return OrderService(order_repository=MockOrderRepository())


@pytest.mark.asyncio
async def test_create_and_get_order(order_service):
    request = CreateOrderRequest(
        product_name="Mechanical keyboard", quantity=2, unit_price=12900
    )
    created = await order_service.create_data(entity=request)
    assert created.id == 1
    assert created.product_name == "Mechanical keyboard"

    fetched = await order_service.get_data_by_data_id(data_id=created.id)
    assert fetched.quantity == 2


@pytest.mark.asyncio
async def test_update_order(order_service):
    created = await order_service.create_data(
        entity=CreateOrderRequest(
            product_name="Mouse pad", quantity=1, unit_price=1500
        )
    )
    updated = await order_service.update_data_by_data_id(
        data_id=created.id, entity=UpdateOrderRequest(quantity=3)
    )
    assert updated.quantity == 3
    assert updated.product_name == "Mouse pad"
```

Run it:

```bash
pytest tests/unit/order/ -v
```

```text
tests/unit/order/test_order_service.py::test_create_and_get_order PASSED
tests/unit/order/test_order_service.py::test_update_order         PASSED
============================== 2 passed in 0.05s ===============================
```

---

## You just wrote

- A DDD-layered domain with zero `Domain → Infrastructure` imports (the pre-commit hook enforces this).
- A service that inherits 7 async CRUD methods from `BaseService` without writing them.
- An ORM model that never leaves the Repository boundary (conversion to `OrderDTO` happens inside `BaseRepository`).
- A router that `Depends` on an IoC-wired service — no manual `get_db()`, no global state.
- A unit test against a protocol-based mock — no database spin-up, no SQLAlchemy patching.
- All of it auto-registered via `discover_domains()`. **Not one line of `src/_apps/` was touched.**

## Next

- **Browse more patterns** — [`examples/`](../../examples/) has small
  self-contained apps contributors can read and paste: CRUD, worker
  tasks, cross-domain dependencies, minimal LLM agent.
- **Add a background job** — same domain, new interface. See
  [`add-worker-task`](../ai-development.md) skill or
  [`src/user/interface/worker/`](../../src/user/interface/worker/).
- **Add an admin page** — auto-generated CRUD UI via NiceGUI. See
  [`add-admin-page`](../ai-development.md) skill or
  [`src/user/interface/admin/`](../../src/user/interface/admin/).
- **Wire an Alembic migration** — the quickstart path uses `create_all`;
  for real environments, generate a migration with
  `alembic revision --autogenerate -m "order: add order table"`.
- **Connect domains** — see the
  [`add-cross-domain`](../ai-development.md) skill for the Protocol-based
  DIP pattern that lets `order` depend on `user` without an import cycle.

Stuck? The reference `user` domain under [`src/user/`](../../src/user/)
is the same pattern with password hashing, batch create, and a worker
task added on top.
