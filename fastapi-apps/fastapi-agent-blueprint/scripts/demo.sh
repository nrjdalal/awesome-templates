#!/usr/bin/env bash
# --------------------------------------------------------------
# Quickstart demo — exercise the user domain + JWT auth via curl.
# Expects a quickstart server running on http://127.0.0.1:8001
# (start it with `make quickstart` in another terminal).
# --------------------------------------------------------------

set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:8001}"

note() { printf "\n\033[1;36m→ %s\033[0m\n" "$*"; }
run()  { printf "\033[0;90m$ %s\033[0m\n" "$*"; eval "$*"; }

if ! command -v curl >/dev/null 2>&1; then
  echo "curl is required but not installed." >&2
  exit 1
fi

# Pretty-print JSON if python3 is available, otherwise pass through.
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
# Auth — register + login to obtain a JWT access token
# --------------------------------------------------------------

note "Register (creates user account + returns JWT token pair)"
REGISTER_BODY='{"username":"alice","full_name":"Alice Liddell","email":"alice@example.com","password":"secret123"}'
REGISTER_RESPONSE="$(curl -sS -X POST "${BASE_URL}/v1/auth/register" \
  -H 'Content-Type: application/json' \
  -d "${REGISTER_BODY}")"
echo "${REGISTER_RESPONSE}" | pretty

ACCESS_TOKEN="$(echo "${REGISTER_RESPONSE}" | python3 -c "import json,sys;print(json.load(sys.stdin)['data']['accessToken'])" 2>/dev/null || echo "")"
REFRESH_TOKEN="$(echo "${REGISTER_RESPONSE}" | python3 -c "import json,sys;print(json.load(sys.stdin)['data']['refreshToken'])" 2>/dev/null || echo "")"

if [ -z "${ACCESS_TOKEN}" ]; then
  note "Register returned no token — trying login with existing alice account"
  LOGIN_BODY='{"username":"alice","password":"secret123"}'
  LOGIN_RESPONSE="$(curl -sS -X POST "${BASE_URL}/v1/auth/login" \
    -H 'Content-Type: application/json' \
    -d "${LOGIN_BODY}")"
  echo "${LOGIN_RESPONSE}" | pretty
  ACCESS_TOKEN="$(echo "${LOGIN_RESPONSE}" | python3 -c "import json,sys;print(json.load(sys.stdin)['data']['accessToken'])" 2>/dev/null || echo "")"
  REFRESH_TOKEN="$(echo "${LOGIN_RESPONSE}" | python3 -c "import json,sys;print(json.load(sys.stdin)['data']['refreshToken'])" 2>/dev/null || echo "")"
fi

if [ -z "${ACCESS_TOKEN}" ]; then
  echo "Could not obtain access token — aborting." >&2
  exit 1
fi

AUTH_HEADER="Authorization: Bearer ${ACCESS_TOKEN}"

# --------------------------------------------------------------
# User CRUD (JWT-protected routes)
# --------------------------------------------------------------

note "Create a second user (JWT-authenticated)"
CREATE_BODY='{"username":"bob","full_name":"Bob Builder","email":"bob@example.com","password":"secret456"}'
CREATE_RESPONSE="$(curl -sS -X POST "${BASE_URL}/v1/user" \
  -H 'Content-Type: application/json' \
  -H "${AUTH_HEADER}" \
  -d "${CREATE_BODY}")"
echo "${CREATE_RESPONSE}" | pretty

USER_ID="$(echo "${CREATE_RESPONSE}" | python3 -c "import json,sys;print(json.load(sys.stdin)['data']['id'])" 2>/dev/null || echo "")"

if [ -z "${USER_ID}" ]; then
  echo "Could not parse created user id from response — aborting." >&2
  exit 1
fi

note "List users (page=1, pageSize=10)"
run "curl -sS '${BASE_URL}/v1/users?page=1&pageSize=10' -H '${AUTH_HEADER}' | pretty"

note "Update the user"
UPDATE_BODY='{"full_name":"Bob Builder (updated)"}'
run "curl -sS -X PUT '${BASE_URL}/v1/user/${USER_ID}' -H 'Content-Type: application/json' -H '${AUTH_HEADER}' -d '${UPDATE_BODY}' | pretty"

note "Delete the user"
run "curl -sS -X DELETE '${BASE_URL}/v1/user/${USER_ID}' -H '${AUTH_HEADER}' | pretty"

# --------------------------------------------------------------
# Auth — refresh token + logout
# --------------------------------------------------------------

if [ -n "${REFRESH_TOKEN}" ]; then
  note "Refresh token"
  run "curl -sS -X POST '${BASE_URL}/v1/auth/refresh' -H 'Content-Type: application/json' -d '{\"refreshToken\":\"${REFRESH_TOKEN}\"}' | pretty"
fi

note "Logout"
run "curl -sS -X POST '${BASE_URL}/v1/auth/logout' -H 'Content-Type: application/json' -H '${AUTH_HEADER}' -d '{\"refreshToken\":\"${REFRESH_TOKEN}\"}' | pretty"

note "Done. API docs: ${BASE_URL}/docs"
