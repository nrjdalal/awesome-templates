#!/usr/bin/env bash
# PostToolUse Hook: Auto-format Python files after Edit/Write
# Runs ruff format + check --fix on edited .py files
# Always exits 0 (formatting failure should not block edits)

set -euo pipefail

HOOK_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "${HOOK_DIR}/../.." && pwd)"
PY_LAUNCHER="${REPO_ROOT}/.agents/shared/harness-python.sh"

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | sh "$PY_LAUNCHER" -c "import json,sys; d=json.load(sys.stdin); print(d.get('tool_input',{}).get('file_path',''))" 2>/dev/null || true)

if [[ -n "$FILE_PATH" && "$FILE_PATH" == *.py && -f "$FILE_PATH" ]]; then
    ruff format "$FILE_PATH" 2>/dev/null || true
    ruff check --fix "$FILE_PATH" 2>/dev/null || true
fi

exit 0
