# Add Async Worker Task — Detailed Procedure

## Default Flow Position

This skill participates in the [Default Coding Flow](../../../../AGENTS.md#default-coding-flow) at the **`implement`** step.

`approach options` upstream is **conditionally mandatory**: required when introducing a new event type, broker pattern, or task interleaving with an existing transactional flow. Skip for routine task additions that follow the established Taskiq pattern.

After implementation, route to:
- `verify` — `/test-domain {name} run` (and an integration smoke run via `make worker`)
- `completion gate` — `/sync-guidelines` if shared docs reference the new task

## Analysis

1. Identify the domain name and task purpose
2. Check if the required method already exists in the domain's Service
3. If not, first perform steps 1-2 (Repository → Service) from the `/add-api` procedure

## Reference
- `src/user/interface/worker/payloads/user_payload.py` — payload pattern
- `src/user/interface/worker/tasks/user_test_task.py` — task pattern
- `src/user/interface/worker/bootstrap/user_bootstrap.py` — worker bootstrap pattern
- `src/_apps/worker/broker.py` — broker configuration

## Implementation Order

### 1. Create Payload Schema
`src/{name}/interface/worker/payloads/{task_name}_payload.py`

> If `payloads/` directory doesn't exist, create it with an empty `__init__.py`.

```python
from src._core.application.dtos.base_payload import BasePayload

class {TaskName}Payload(BasePayload):
    # Define only the fields needed for this specific task message
    ...
```

### 2. Create Task Function
`src/{name}/interface/worker/tasks/{task_name}_task.py`

```python
from dependency_injector.wiring import Provide, inject
from src._apps.worker.broker import broker
from src._core.config import settings
from src.{name}.domain.services.{name}_service import {Name}Service
from src.{name}.infrastructure.di.{name}_container import {Name}Container
from src.{name}.interface.worker.payloads.{name}_payload import {TaskName}Payload

@broker.task(task_name=f"{settings.task_name_prefix}.{name}.{task_name}")
@inject
async def {task_name}_task(
    {name}_service: {Name}Service = Provide[{Name}Container.{name}_service],
    **kwargs,
) -> None:
    payload = {TaskName}Payload.model_validate(kwargs)
    await {name}_service.{method}(entity=payload)
```

### 3. Update Worker Bootstrap
In `src/{name}/interface/worker/bootstrap/{name}_bootstrap.py`:
- Import the new task module
- Add to `wire(modules=[..., {task_name}_task])`

### 4. Verify/Add Service Method
- Check if the Service method that the task will call exists
- If not, add the method to the Service (and Repository if needed)

## Core Rules
- Task functions are thin adapters: receive `**kwargs`, validate via Payload, then call Service only
- Payloads define the explicit message contract (same principle as Request for HTTP)
- When fields match: pass payload directly to Service (`entity=payload`)
- When fields differ: create DTO and convert (`DTO(**payload.model_dump(), extra=...)`)
- `extra="forbid"` on Payload catches producer-side contract violations early
- Business logic must reside in the Service
- Model objects must not be exposed to tasks
- DI pattern: see `docs/ai/shared/project-dna.md` §5
- Conversion Patterns: see `docs/ai/shared/project-dna.md` §6

## Post-completion Verification
1. Run pre-commit
2. Verify broker import: `python -c "from src.{name}.interface.worker.tasks.{task_name}_task import {task_name}_task; print('OK')"`
