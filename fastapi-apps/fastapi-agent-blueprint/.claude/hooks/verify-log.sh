#!/usr/bin/env bash
# PostToolUse Bash Hook — record verify-class commands to the session
# verify-log (#334). Always exits 0: bookkeeping must never block a tool call
# (HC-3.3). Mirrors the wrapper shape of the sibling PostToolUse hooks.
HOOK_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "${HOOK_DIR}/../.." && pwd)"
PY_LAUNCHER="${REPO_ROOT}/.agents/shared/harness-python.sh"

INPUT=$(cat)
echo "$INPUT" | sh "$PY_LAUNCHER" "${HOOK_DIR}/verify_log.py" || true
exit 0
