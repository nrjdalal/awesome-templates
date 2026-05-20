# 041. Multi-backend Infrastructure Layout — Persistence Umbrella and Backend Subfolders

- Status: Accepted
- Date: 2026-04-20
- Related issue: #80 (End-to-end RAG example)
- Supersedes layout from: [ADR 006](006-ddd-layered-architecture.md) (Per-domain layered architecture, unaffected but infrastructure sibling layout evolved), [ADR 034](archive/034-s3vectors-vectorstore-pattern.md) (S3 Vectors layout)

## Summary

`src/_core/infrastructure/` now follows a two-part convention for multi-backend abstractions:

1. **Abstractions with the same role group under an umbrella.** RDB and NoSQL share the "CRUD data persistence" role, so `database/` and `dynamodb/` move under `persistence/rdb/` and `persistence/nosql/dynamodb/`.
2. **Backends of the same abstraction split into subfolders.** `vectors/` keeps its top-level position (the role is retrieval, not persistence) but its two backends live in `vectors/s3/` and `vectors/in_memory/`, with the shared `vector_model.py` at the root.

Abstractions with a single implementation (`embedding/`, `llm/`, `taskiq/`, `http/`, `storage/`) stay flat — umbrellas and subfolders are introduced only where there is genuine multiplicity.

## Background

Two prior structural moves led here:

1. ADR 034 introduced `_core/infrastructure/s3vectors/` for the AWS S3 Vectors backend.
2. ADR 040 added an in-memory vector store (for `make quickstart`) under the peer directory `_core/infrastructure/in_memory_vectors/`.

Mid-implementation of #80, two observations surfaced:

- The in-memory store already imports the shared `VectorModel` from the sibling folder — the split hid an actual coupling rather than preventing one. Consolidation was required.
- Once consolidated, "why does `vectors/` have subfolders but `database/` + `dynamodb/` live as siblings at the same level?" became a fair question. The answer revealed an inconsistency: the project had no declared convention for multi-backend layout. This ADR declares one.

## Problem

### 1. Multi-backend splits without convention

Three infra abstractions in this repo have more than one backend:

| Abstraction | Backends | Old layout |
|---|---|---|
| CRUD persistence | RDB, DynamoDB | `database/`, `dynamodb/` — siblings |
| Vector retrieval | S3 Vectors, in-memory | `s3vectors/`, `in_memory_vectors/` — siblings |
| Object storage | S3, MinIO | `storage/` — merged (same class, different params) |

The third case (`storage/`) is genuinely flat because both backends share one class. The first two were split purely because they were added at different times, not because of a design rule. Contributors could not predict where a new backend should go.

### 2. Conflating persistence and retrieval

Placing `vectors/` alongside `database/` suggested they are alternative data stores. In practice, consumer domains compose them — `DocumentRepository` (RDB, CRUD) and `DocumentChunkVectorStore` (vectors, similarity search) coexist for the same document. A flat layout did not reflect this complementary relationship.

## Decision

### 1. Umbrella folder for same-role abstractions

```
_core/infrastructure/
├── persistence/             # CRUD data persistence
│   ├── rdb/                 # (was database/)
│   │   ├── base_repository.py
│   │   ├── database.py
│   │   └── config.py
│   └── nosql/
│       └── dynamodb/        # (was dynamodb/)
│           ├── base_dynamo_repository.py
│           ├── dynamodb_client.py
│           └── dynamo_model.py
└── vectors/                 # Vector retrieval — kept top-level (different role)
    ├── vector_model.py      # Shared: VectorModel, VectorModelMeta, VectorData
    ├── s3/
    │   ├── base_store.py    # BaseS3VectorStore
    │   ├── client.py        # S3VectorClient
    │   └── exceptions.py    # S3VectorException hierarchy
    └── in_memory/
        └── base_store.py    # BaseInMemoryVectorStore
```

Two rules applied:

- **Rule A — Umbrella for same role, different abstractions.** `rdb` and `nosql` share the "CRUD persistence" role but expose different Protocols (`BaseRepositoryProtocol` vs `BaseDynamoRepositoryProtocol`). They get a shared `persistence/` roof.
- **Rule B — Subfolders for same abstraction, different backends.** S3 Vectors and in-memory implement the same `BaseVectorStoreProtocol` and share `VectorModel`. They get peer subfolders inside `vectors/`.

### 2. Vectors stays separate from persistence

`vectors/` does not move under `persistence/`. The vector store's centre is `search(VectorQuery)` — a retrieval / similarity operation, not CRUD. `BaseVectorStoreProtocol` and `BaseRepositoryProtocol` are orthogonal APIs; one is not a substitute for the other. Grouping them would dilute the meaning of "persistence".

### 3. Single-implementation abstractions stay flat

`embedding/`, `llm/`, `taskiq/`, `http/`, `storage/`, `admin/`, `di/` each have one adapter / implementation today. No umbrella, no subfolder — flat stays readable. Adding ceremony to empty categories is overhead with zero current benefit.

### 4. Filename simplification in `vectors/{s3,in_memory}/`

Because the subfolder name already encodes the backend, prefixes are dropped:

| Before | After |
|---|---|
| `base_s3vector_store.py` | `s3/base_store.py` |
| `s3vector_client.py` | `s3/client.py` |
| `exceptions.py` (S3-specific) | `s3/exceptions.py` |
| `base_in_memory_vector_store.py` | `in_memory/base_store.py` |

Class names keep their backend in the identifier — `BaseS3VectorStore`, `S3VectorClient`, `BaseInMemoryVectorStore` — so IDE autocomplete and grep are unambiguous even across subfolders.

### 5. Shared vector model stays at `vectors/` root

`vector_model.py` holds `VectorModel` / `VectorModelMeta` / `VectorData` — the contract that both backends implement. It lives at `vectors/` (not under `s3/` or `in_memory/`) because it belongs to neither backend alone.

### 6. Domain-side infrastructure stays flat

Domain packages (`src/user/infrastructure/database/`, `src/docs/infrastructure/vectors/`, etc.) do **not** adopt the umbrella. Rationale: a domain has already chosen its backend(s); the folder names there describe *which* adapter the domain uses, not a catalogue of options. Umbrella structure is a `_core` concern, not a per-domain concern.

### 7. `S3VECTORS_*` env vars, settings fields, and `migrations/` CLI folders keep their product names

Env vars (`S3VECTORS_BUCKET_NAME`), Settings fields (`settings.s3vectors_*`), and CLI tool folders (`migrations/s3vectors/`, `migrations/dynamodb/`) continue to reference the AWS product name directly. They configure specific AWS products, not the generic abstraction, and do not change with the Python module layout.

## Consequences

- **Every consumer import path changes** for `database/`, `dynamodb/`, and the three split vector files. Not optional — covered in this PR.
- **Future backend additions get a clear rule.** Adding Qdrant? It goes in `vectors/qdrant/`. Adding MongoDB? `persistence/nosql/mongodb/`. Adding a second LLM adapter? Today still flat; introduce subfolders only when the third adapter arrives.
- **Umbrella introduction is localised, not wholesale.** The `_apps/` entrypoints (`server`, `worker`, `admin`) stay flat; so do all single-implementation infra folders. This ADR sets a *threshold* for when umbrellas are worth introducing, not a mandate to apply them everywhere.
- **ADR 034 remains valid for the S3 Vectors design itself** — index schema, batch limits, filter contract. Only the paths change (tracked under "Supersedes layout from").

## Alternatives Considered

- **Keep `vectors/` flat (5 files, two backend groups mixed).** Rejected: the `exceptions.py` / `base_in_memory_vector_store.py` split was legible via filename prefix, but the same argument would apply to `persistence/` if it had stayed flat — and the convention should be uniform. Flat-with-prefix is acceptable for 2–3 files total; beyond that, subfolders are clearer.
- **Put `vectors/` under `persistence/vectors/`.** Rejected for the reasons in Decision §2. A vector store's role is retrieval, not persistence; colocation would imply they are alternatives.
- **Introduce umbrellas across the board** (`ai/{embedding,llm}/`, `network/{http}/`, `execution/{taskiq}/`, etc.). Rejected: YAGNI. Umbrellas with one occupant add path depth without clarity benefit. Revisit when any such area grows to 2+ implementations.
- **Apply umbrella to domain infrastructure too** (`src/{domain}/infrastructure/persistence/rdb/models/`). Rejected: domain infra names describe adopted backends, not a catalogue of choices. The umbrella serves no purpose there and would change every per-domain scaffolding path and tutorial.
- **One ADR per decision** (split into 041a "vector consolidation" + 041b "persistence umbrella" + 041c "vector subfolder split"). Rejected: the three moves are three applications of the same policy ("backend multiplicity deserves structural marking"). Splitting them would hide the policy behind three narrower documents.
