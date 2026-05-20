#!/usr/bin/env bash
# --------------------------------------------------------------
# RAG quickstart demo — end-to-end showcase of the rag domain.
#
# Seeds three sample documents, lists them, runs a natural-language
# query against the retrieved context, and prints the structured
# answer with citations.
#
# Expects a quickstart server running on http://127.0.0.1:8001
# (start it with `make quickstart` in another terminal).
#
# Default providers in quickstart mode:
#   - Vector store : InMemory (process-local cosine)
#   - Embedder     : Stub (keyword bag-of-words, 128-dim)
#   - LLM agent    : Stub (templated retrieval-based answer)
#
# For real embeddings and real LLM answers:
#   1. set EMBEDDING_PROVIDER + EMBEDDING_MODEL in _env/quickstart.env
#   2. set LLM_PROVIDER + LLM_MODEL + credentials
#   3. optionally set VECTOR_STORE_TYPE=s3vectors for persistence
# --------------------------------------------------------------

set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:8001}"

note() { printf "\n\033[1;36m→ %s\033[0m\n" "$*"; }
run()  { printf "\033[0;90m$ %s\033[0m\n" "$*"; eval "$*"; }

if ! command -v curl >/dev/null 2>&1; then
  echo "curl is required but not installed." >&2
  exit 1
fi

pretty() {
  if command -v python3 >/dev/null 2>&1; then
    python3 -m json.tool 2>/dev/null || cat
  else
    cat
  fi
}

note "Health check"
run "curl -sS '${BASE_URL}/health' | pretty"

# --------------------------------------------------------------
# Seed three sample documents
# --------------------------------------------------------------

note "Seed document 1 — FastAPI overview"
DOC1_BODY='{
  "title": "FastAPI Framework Overview",
  "source": "https://fastapi.tiangolo.com",
  "content": "FastAPI is a modern Python web framework for building APIs. It leverages type hints for automatic request validation via Pydantic and generates OpenAPI documentation automatically. FastAPI is built on Starlette for async HTTP handling and supports dependency injection out of the box. Developers choose FastAPI for its speed, developer ergonomics, and first-class async support."
}'
run "curl -sS -X POST '${BASE_URL}/v1/docs/documents' -H 'Content-Type: application/json' -d '${DOC1_BODY}' | pretty"

note "Seed document 2 — DDD layered architecture"
DOC2_BODY='{
  "title": "Domain-Driven Design Layers",
  "source": "internal-notes",
  "content": "Domain-Driven Design organizes code around business domains rather than technical concerns. The typical layered architecture separates Interface, Application, Domain, and Infrastructure. The Domain layer contains business logic and must not depend on infrastructure details. The Infrastructure layer implements persistence and external integrations. Interfaces invert control via protocols or dependency injection."
}'
run "curl -sS -X POST '${BASE_URL}/v1/docs/documents' -H 'Content-Type: application/json' -d '${DOC2_BODY}' | pretty"

note "Seed document 3 — Retrieval-Augmented Generation"
DOC3_BODY='{
  "title": "Retrieval-Augmented Generation Primer",
  "source": "docs/rag-primer.md",
  "content": "Retrieval-Augmented Generation combines a vector database with a large language model. A user question is embedded into a vector, matched against an index of document chunks, and the top results are supplied as context to the LLM. This approach reduces hallucinations because the model answers from retrieved evidence rather than parametric memory alone. Citations link each answer back to the source chunk that supported it."
}'
run "curl -sS -X POST '${BASE_URL}/v1/docs/documents' -H 'Content-Type: application/json' -d '${DOC3_BODY}' | pretty"

# --------------------------------------------------------------
# List seeded documents
# --------------------------------------------------------------

note "List indexed documents"
run "curl -sS '${BASE_URL}/v1/docs/documents?page=1&pageSize=10' | pretty"

# --------------------------------------------------------------
# Run a natural-language query
# --------------------------------------------------------------

note "Query: 'What does retrieval-augmented generation do with citations?'"
QUERY_BODY='{
  "question": "What does retrieval-augmented generation do with citations?",
  "top_k": 3
}'
run "curl -sS -X POST '${BASE_URL}/v1/docs/query' -H 'Content-Type: application/json' -d '${QUERY_BODY}' | pretty"

note "Done. API docs: ${BASE_URL}/docs | Admin: ${BASE_URL}/admin/docs"
