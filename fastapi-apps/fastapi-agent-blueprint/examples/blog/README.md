# Blog Example — Protocol-based Cross-Domain DIP

Two domains (`author`, `post`) where `post` depends on `author` **via
`AuthorRepositoryProtocol`, not via a direct repository import**. This
mirrors the precedent set by `src/auth` depending on `src/user` via
`UserRepositoryProtocol`.

## Domains

### Author
Standard CRUD domain with minimal fields (`id`, `display_name`).

### Post
Standard CRUD domain (`id`, `author_id`, `title`, `body`). The
`PostService` receives an `AuthorRepositoryProtocol` via DI and uses it
to resolve the author's `display_name` when returning post responses.

## Key File: Protocol Boundary

`author/domain/protocols/author_repository_protocol.py` — the **provider
domain owns the protocol**; the post domain imports it from there. This
matches the project's `add-cross-domain` convention and the `src/auth →
src/user` precedent.

Coupling surface (deliberate, minimal):
- `post.PostService` imports `author.AuthorRepositoryProtocol`
- `post.AuthorRepositoryProtocol` itself references `author.AuthorDTO`
  (so the `post` domain layer depends on `author`'s DTO **type**)
- `post.PostContainer` wires the concrete `author.AuthorRepository` to
  the protocol — the only place post touches author *infrastructure*

The domains aren't fully independently deployable — `post` needs
`author`'s domain types — but the infrastructure boundary stays clean
and the consumer can be tested against a mock implementing the protocol.

## Endpoints

### Author
| Method | Path                       | Description   |
|--------|----------------------------|---------------|
| POST   | `/v1/author`               | Create author |
| GET    | `/v1/authors`              | List authors  |
| GET    | `/v1/author/{author_id}`   | Get author    |
| PUT    | `/v1/author/{author_id}`   | Update author |
| DELETE | `/v1/author/{author_id}`   | Delete author |

### Post
| Method | Path                  | Description |
|--------|-----------------------|-------------|
| POST   | `/v1/post`            | Create post |
| GET    | `/v1/posts`           | List posts  |
| GET    | `/v1/post/{post_id}`  | Get post    |
| PUT    | `/v1/post/{post_id}`  | Update post |
| DELETE | `/v1/post/{post_id}`  | Delete post |

## Verification

```bash
# 1. Copy domains into src/
cp -r examples/blog/author/ src/author/
cp -r examples/blog/post/ src/post/

# 2. Start the server (quickstart serves on 8001)
make quickstart

# 3. Create an author
curl -X POST http://localhost:8001/v1/author \
  -H "Content-Type: application/json" \
  -d '{"display_name": "Alice"}'

# 4. Create a post referencing the author
curl -X POST http://localhost:8001/v1/post \
  -H "Content-Type: application/json" \
  -d '{"author_id": 1, "title": "Hello World", "body": "First post!"}'

# 5. Get the post — response includes author_display_name
curl http://localhost:8001/v1/post/1

# 6. Run tests
pytest tests/unit/blog/ -v
```
