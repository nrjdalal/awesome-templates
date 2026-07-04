#!/usr/bin/env bash
# PostToolUse Edit|Write Hook — mid-task stage-gate advisory (ADR 050, #268).
# Always exits 0 (advisory only, never blocks tool use — ADR050-G1).
HOOK_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "${HOOK_DIR}/../.." && pwd)"
PY_LAUNCHER="${REPO_ROOT}/.agents/shared/harness-python.sh"

INPUT=$(cat)
echo "$INPUT" | sh "$PY_LAUNCHER" "${HOOK_DIR}/post_tool_stage_gate.py" || true
exit 0
