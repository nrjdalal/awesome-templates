#!/usr/bin/env bash
# PostToolUse Edit|Write Hook — verify-first reminder (Phase 3 of #117 / #122).
# Always exits 0 (informational only, never blocks tool use — HC-3.3).
HOOK_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "${HOOK_DIR}/../.." && pwd)"
PY_LAUNCHER="${REPO_ROOT}/.agents/shared/harness-python.sh"

INPUT=$(cat)
echo "$INPUT" | sh "$PY_LAUNCHER" "${HOOK_DIR}/verify_first.py" || true
exit 0
