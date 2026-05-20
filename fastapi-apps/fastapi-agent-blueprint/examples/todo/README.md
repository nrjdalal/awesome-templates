# Todo Example

A minimal CRUD example mirroring the [`src/user/`](../../src/user/) layout.
> **Note:** Reference code only. Not auto-wired. To run it, copy into `src/todo/` or add a manual bootstrap call.
## Endpoints

- `POST /v1/todo` — Create a todo
- `GET /v1/todos` — List all todos
- `GET /v1/todo/{todo_id}` — Get a todo by ID
- `PUT /v1/todo/{todo_id}` — Update a todo
- `DELETE /v1/todo/{todo_id}` — Delete a todo

## Quick Start

```bash
curl -X POST http://localhost:8001/v1/todo \
  -H "Content-Type: application/json" \
  -d '{"title": "My first todo"}'

curl http://localhost:8001/v1/todos

curl -X DELETE http://localhost:8001/v1/todo/{todo_id}
```
