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

# python3 is not optional: the token extraction below and the envelope
# assertions both need it. Saying so here beats failing later with a
# confusing "Could not obtain access token".
for dep in curl python3; do
  if ! command -v "${dep}" >/dev/null 2>&1; then
    echo "${dep} is required but not installed." >&2
    exit 1
  fi
done

# Pretty-print JSON.
pretty() { python3 -m json.tool 2>/dev/null || cat; }

# --------------------------------------------------------------
# Envelope assertions.
#
# Printing a response is not the same as checking it. Until these
# existed, this script printed a 401 for every single /v1/docs call and
# still exited 0 — which is exactly how the auth requirement added by
# f790fea went unnoticed for two months. Every call expecting a success
# envelope now goes through `check`.
# --------------------------------------------------------------

RESPONSE=""

# check CURL_COMMAND — run it, pretty-print the body, and abort unless the
# response envelope reports success. Pass the curl invocation WITHOUT a
# trailing `| pretty`; this helper prints for you.
check() {
  printf "\033[0;90m$ %s\033[0m\n" "$*"
  RESPONSE="$(eval "$*")"
  echo "${RESPONSE}" | pretty
  assert_success "$*"
}

assert_success() {
  echo "${RESPONSE}" \
    | python3 -c "import json,sys; sys.exit(0 if json.load(sys.stdin).get('success') is True else 1)" \
      2>/dev/null && return 0
  echo "" >&2
  echo "The response above is not a success envelope — aborting." >&2
  echo "  request: $1" >&2
  exit 1
}

# /health is outside the SuccessResponse envelope, so it gets its own check.
note "Health check"
printf "\033[0;90m$ %s\033[0m\n" "curl -sS '${BASE_URL}/health'"
HEALTH="$(curl -sS "${BASE_URL}/health")"
echo "${HEALTH}" | pretty
echo "${HEALTH}" \
  | python3 -c "import json,sys; sys.exit(0 if json.load(sys.stdin).get('status') == 'ok' else 1)" 2>/dev/null || {
  echo "Server is not healthy at ${BASE_URL} — is \`make quickstart\` running?" >&2
  exit 1
}

# --------------------------------------------------------------
# Auth — every /v1/docs route is gated on a customer-realm token
# (`Depends(get_current_user)`), so obtain one before seeding.
# Register is idempotent here only in the sense that a second run
# falls back to login with the same credentials.
# --------------------------------------------------------------

note "Register (or log in) to obtain a customer JWT"
REGISTER_BODY='{"username":"alice","full_name":"Alice Liddell","email":"alice@example.com","password":"secret123"}'
REGISTER_RESPONSE="$(curl -sS -X POST "${BASE_URL}/v1/auth/register" \
  -H 'Content-Type: application/json' \
  -d "${REGISTER_BODY}")"

ACCESS_TOKEN="$(echo "${REGISTER_RESPONSE}" | python3 -c "import json,sys;print(json.load(sys.stdin)['data']['accessToken'])" 2>/dev/null || echo "")"

if [ -z "${ACCESS_TOKEN}" ]; then
  LOGIN_BODY='{"username":"alice","password":"secret123"}'
  LOGIN_RESPONSE="$(curl -sS -X POST "${BASE_URL}/v1/auth/login" \
    -H 'Content-Type: application/json' \
    -d "${LOGIN_BODY}")"
  ACCESS_TOKEN="$(echo "${LOGIN_RESPONSE}" | python3 -c "import json,sys;print(json.load(sys.stdin)['data']['accessToken'])" 2>/dev/null || echo "")"
fi

if [ -z "${ACCESS_TOKEN}" ]; then
  echo "Could not obtain access token — aborting." >&2
  exit 1
fi

AUTH_HEADER="Authorization: Bearer ${ACCESS_TOKEN}"
echo "Obtained a customer access token."

# --------------------------------------------------------------
# Seed three sample documents
# --------------------------------------------------------------

note "Seed document 1 — FastAPI overview"
DOC1_BODY='{
  "title": "FastAPI Framework Overview",
  "source": "https://fastapi.tiangolo.com",
  "content": "FastAPI is a modern Python web framework for building APIs. It leverages type hints for automatic request validation via Pydantic and generates OpenAPI documentation automatically. FastAPI is built on Starlette for async HTTP handling and supports dependency injection out of the box. Developers choose FastAPI for its speed, developer ergonomics, and first-class async support."
}'
check "curl -sS -X POST '${BASE_URL}/v1/docs/documents' -H 'Content-Type: application/json' -H '${AUTH_HEADER}' -d '${DOC1_BODY}'"

note "Seed document 2 — DDD layered architecture"
DOC2_BODY='{
  "title": "Domain-Driven Design Layers",
  "source": "internal-notes",
  "content": "Domain-Driven Design organizes code around business domains rather than technical concerns. The typical layered architecture separates Interface, Application, Domain, and Infrastructure. The Domain layer contains business logic and must not depend on infrastructure details. The Infrastructure layer implements persistence and external integrations. Interfaces invert control via protocols or dependency injection."
}'
check "curl -sS -X POST '${BASE_URL}/v1/docs/documents' -H 'Content-Type: application/json' -H '${AUTH_HEADER}' -d '${DOC2_BODY}'"

note "Seed document 3 — Retrieval-Augmented Generation"
DOC3_BODY='{
  "title": "Retrieval-Augmented Generation Primer",
  "source": "docs/rag-primer.md",
  "content": "Retrieval-Augmented Generation combines a vector database with a large language model. A user question is embedded into a vector, matched against an index of document chunks, and the top results are supplied as context to the LLM. This approach reduces hallucinations because the model answers from retrieved evidence rather than parametric memory alone. Citations link each answer back to the source chunk that supported it."
}'
check "curl -sS -X POST '${BASE_URL}/v1/docs/documents' -H 'Content-Type: application/json' -H '${AUTH_HEADER}' -d '${DOC3_BODY}'"

# --------------------------------------------------------------
# List seeded documents
# --------------------------------------------------------------

note "List indexed documents"
check "curl -sS '${BASE_URL}/v1/docs/documents?page=1&pageSize=10' -H '${AUTH_HEADER}'"

# --------------------------------------------------------------
# Run a natural-language query
# --------------------------------------------------------------

note "Query: 'What does retrieval-augmented generation do with citations?'"
QUERY_BODY='{
  "question": "What does retrieval-augmented generation do with citations?",
  "top_k": 3
}'
check "curl -sS -X POST '${BASE_URL}/v1/docs/query' -H 'Content-Type: application/json' -H '${AUTH_HEADER}' -d '${QUERY_BODY}'"

note "Done. API docs: ${BASE_URL}/docs | Admin: ${BASE_URL}/admin/docs"
