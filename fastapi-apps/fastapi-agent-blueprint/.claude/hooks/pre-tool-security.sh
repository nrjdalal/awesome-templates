#!/usr/bin/env bash
# PreToolUse Hook: Security pattern check before code writing
# Exit 0 = allow, Exit 2 = block

HOOK_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "${HOOK_DIR}/../.." && pwd)"
PY_LAUNCHER="${REPO_ROOT}/.agents/shared/harness-python.sh"

INPUT=$(cat)
echo "$INPUT" | sh "$PY_LAUNCHER" "${HOOK_DIR}/pre_tool_security.py"
