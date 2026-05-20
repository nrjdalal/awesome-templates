#!/usr/bin/env bash
# UserPromptSubmit Hook: Exception-token parser (Phase 2 of #117 / #121)
# Informational only — exit 0 in all cases, never blocks prompt submission.

HOOK_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "${HOOK_DIR}/../.." && pwd)"
PY_LAUNCHER="${REPO_ROOT}/.agents/shared/harness-python.sh"

INPUT=$(cat)
echo "$INPUT" | sh "$PY_LAUNCHER" "${HOOK_DIR}/user_prompt_submit.py"
