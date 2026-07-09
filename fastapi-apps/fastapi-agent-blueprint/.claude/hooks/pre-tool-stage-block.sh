#!/usr/bin/env bash
# PreToolUse Edit|Write Hook — plan→execute boundary hard block (ADR 054).
# Exit 0 = allow, Exit 2 = block. Unlike stage-gate.sh (advisory, always
# exits 0), this propagates the Python exit code so exit 2 blocks the edit.
# The harness-python launcher itself exits 0 when no interpreter resolves
# (fail-open, ADR054-G5), so a broken environment never wedges editing.

HOOK_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "${HOOK_DIR}/../.." && pwd)"
PY_LAUNCHER="${REPO_ROOT}/.agents/shared/harness-python.sh"
SCRIPT="${HOOK_DIR}/pre_tool_stage_block.py"

# Fail-open (ADR054-G5): a missing/unreadable hook script or launcher must ALLOW
# the edit. Without this guard the interpreter's own exit 2 on a missing script
# would masquerade as a block (exit 2 == BLOCK), the one fail-CLOSED path.
[ -r "$SCRIPT" ] && [ -r "$PY_LAUNCHER" ] || exit 0

INPUT=$(cat)
echo "$INPUT" | sh "$PY_LAUNCHER" "$SCRIPT"
