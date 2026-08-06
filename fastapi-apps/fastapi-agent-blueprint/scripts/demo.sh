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
# existed, a call that came back `{"success": false, ...}` was printed
# in red-flag detail and then cheerfully stepped over, so this script
# and `demo-rag.sh` both reported success against a completely broken
# API. That is how the #199/#218 admin-realm breakage stayed invisible
# from 2026-05-27 until it was reported: nothing ever failed.
#
# Every call expecting a success envelope now goes through `check`.
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
# Admin realm — /v1/user* is gated on Depends(require_admin) since
# #199, re-pointed to the admin token realm by #218. The customer
# token above cannot reach it, and neither can the quickstart
# bootstrap admin (require_admin rejects is_bootstrap_admin, and the
# token login rejects bootstrap + temp-password accounts). Seed a
# real admin the way the NiceGUI setup wizard would.
# --------------------------------------------------------------

DEMO_ADMIN_USER="${DEMO_ADMIN_USER:-demoadmin}"
DEMO_ADMIN_SECRET="${DEMO_ADMIN_SECRET:-demoadmin123}"

note "Seed the demo admin (quickstart only — refuses to run in stg/prod)"
run "uv run python scripts/seed_demo_admin.py --env quickstart --username '${DEMO_ADMIN_USER}' --secret '${DEMO_ADMIN_SECRET}'"

note "Admin login (separate token realm from the customer token above)"
ADMIN_LOGIN_BODY="{\"username\":\"${DEMO_ADMIN_USER}\",\"password\":\"${DEMO_ADMIN_SECRET}\"}"
ADMIN_LOGIN_RESPONSE="$(curl -sS -X POST "${BASE_URL}/v1/admin/login" \
  -H 'Content-Type: application/json' \
  -d "${ADMIN_LOGIN_BODY}")"

ADMIN_ACCESS_TOKEN="$(echo "${ADMIN_LOGIN_RESPONSE}" | python3 -c "import json,sys;print(json.load(sys.stdin)['data']['accessToken'])" 2>/dev/null || echo "")"

if [ -z "${ADMIN_ACCESS_TOKEN}" ]; then
  echo "${ADMIN_LOGIN_RESPONSE}" | pretty
  echo "Could not obtain an admin access token — aborting." >&2
  exit 1
fi

ADMIN_AUTH_HEADER="Authorization: Bearer ${ADMIN_ACCESS_TOKEN}"
echo "Obtained an admin-realm access token."

# --------------------------------------------------------------
# User CRUD (admin-realm protected routes)
# --------------------------------------------------------------

note "Create a second user (admin-authenticated)"
CREATE_BODY='{"username":"bob","full_name":"Bob Builder","email":"bob@example.com","password":"secret456"}'
CREATE_RESPONSE="$(curl -sS -X POST "${BASE_URL}/v1/user" \
  -H 'Content-Type: application/json' \
  -H "${ADMIN_AUTH_HEADER}" \
  -d "${CREATE_BODY}")"
echo "${CREATE_RESPONSE}" | pretty

USER_ID="$(echo "${CREATE_RESPONSE}" | python3 -c "import json,sys;print(json.load(sys.stdin)['data']['id'])" 2>/dev/null || echo "")"

if [ -z "${USER_ID}" ]; then
  echo "Could not parse created user id from response — aborting." >&2
  exit 1
fi

note "List users (page=1, pageSize=10)"
check "curl -sS '${BASE_URL}/v1/users?page=1&pageSize=10' -H '${ADMIN_AUTH_HEADER}'"

note "Update the user"
UPDATE_BODY='{"full_name":"Bob Builder (updated)"}'
check "curl -sS -X PUT '${BASE_URL}/v1/user/${USER_ID}' -H 'Content-Type: application/json' -H '${ADMIN_AUTH_HEADER}' -d '${UPDATE_BODY}'"

note "Delete the user"
check "curl -sS -X DELETE '${BASE_URL}/v1/user/${USER_ID}' -H '${ADMIN_AUTH_HEADER}'"

# --------------------------------------------------------------
# Auth — refresh token + logout
# --------------------------------------------------------------

if [ -n "${REFRESH_TOKEN}" ]; then
  note "Refresh token"
  check "curl -sS -X POST '${BASE_URL}/v1/auth/refresh' -H 'Content-Type: application/json' -d '{\"refreshToken\":\"${REFRESH_TOKEN}\"}'"
  # Rotation revokes the token just spent, so log out with the new one.
  REFRESH_TOKEN="$(echo "${RESPONSE}" | python3 -c "import json,sys;print(json.load(sys.stdin)['data']['refreshToken'])" 2>/dev/null || echo "${REFRESH_TOKEN}")"
fi

note "Logout"
check "curl -sS -X POST '${BASE_URL}/v1/auth/logout' -H 'Content-Type: application/json' -H '${AUTH_HEADER}' -d '{\"refreshToken\":\"${REFRESH_TOKEN}\"}'"

note "Done. API docs: ${BASE_URL}/docs"
