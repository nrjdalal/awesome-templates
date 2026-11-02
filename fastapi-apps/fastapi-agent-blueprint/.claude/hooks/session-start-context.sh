#!/usr/bin/env bash
# SessionStart Hook: Inject work-ledger context summary into Claude's session.
# stdout is injected as a system message by Claude Code.
# Always exits 0 (advisory only; fail-open per HC-5.5).

set -euo pipefail

HOOK_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "${HOOK_DIR}/../.." && pwd)"
SHARED_DIR="${REPO_ROOT}/.agents/shared"
PY_LAUNCHER="${REPO_ROOT}/.agents/shared/harness-python.sh"

# The payload's `cwd` names the session's tree, whose ledger this summary is
# about — this copy can be running for another checkout's session (#425).
INPUT=""
[ -t 0 ] || INPUT=$(cat)

SUMMARY=$(printf '%s' "$INPUT" | PYTHONPATH="${SHARED_DIR}" sh "$PY_LAUNCHER" -c "
import json, sys
sys.path.insert(0, '${SHARED_DIR}')
try:
    from governor import resolve_session_roots
    from work_ledger import build_session_summary
    try:
        payload = json.loads(sys.stdin.read() or '{}')
    except ValueError:
        payload = {}
    roots = resolve_session_roots(payload)
    s = None if roots.rejected else build_session_summary(state_root=roots.state_root)
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
