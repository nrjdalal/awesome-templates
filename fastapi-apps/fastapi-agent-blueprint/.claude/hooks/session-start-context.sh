#!/usr/bin/env bash
# SessionStart Hook: Inject work-ledger context summary into Claude's session.
# stdout is injected as a system message by Claude Code.
# Always exits 0 (advisory only; fail-open per HC-5.5).

set -euo pipefail

HOOK_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "${HOOK_DIR}/../.." && pwd)"
SHARED_DIR="${REPO_ROOT}/.agents/shared"
PY_LAUNCHER="${REPO_ROOT}/.agents/shared/harness-python.sh"

SUMMARY=$(PYTHONPATH="${SHARED_DIR}" sh "$PY_LAUNCHER" -c "
import sys
sys.path.insert(0, '${SHARED_DIR}')
try:
    from work_ledger import build_session_summary
    s = build_session_summary()
    if s:
        print(s)
except Exception:
    pass
" 2>/dev/null) || SUMMARY=""

if [ -n "$SUMMARY" ]; then
    echo ""
    echo "$SUMMARY"
    echo ""
fi

exit 0
