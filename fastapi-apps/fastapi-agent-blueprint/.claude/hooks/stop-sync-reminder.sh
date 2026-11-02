#!/usr/bin/env bash
# Stop Hook: Recommend /sync-guidelines when foundation/structure files changed
# Uses git diff to detect ALL changes (Edit, Write, Bash, Subagent)
# Always exit 0 (advisory only)
#
# AGENT_LOCALE rendering (issue #133): translated headers/labels are
# resolved by invoking the shared Python launcher with `-m governor.locale KEY` from the canonical
# locale data file. This shell file itself contains no Korean — every
# fallback string is the canonical English source per Issue AC.

set -euo pipefail

HOOK_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "${HOOK_DIR}/../.." && pwd)"
SHARED_DIR="${REPO_ROOT}/.agents/shared"
PY_LAUNCHER="${REPO_ROOT}/.agents/shared/harness-python.sh"

# This copy can be running for another checkout's session: Claude Code desktop
# runs a worktree session's hooks from the main checkout. The Stop payload's
# `cwd` names the session's tree, and every git call and state write below works
# there (#425). No payload (a manual run) keeps this checkout, the pre-#425
# behaviour. With a payload, `none` (no cwd) keeps it too and `rejected` skips
# the hook rather than report this checkout's changes and state as the session's.

# HC-5.5 fallback for when the resolver never answered (no interpreter, a broken
# import): mirrors governor.paths._inside_this_checkout. True when the payload
# has no cwd, or its cwd is this checkout or a directory of it outside any
# nested checkout (a linked worktree has its own .git). A cwd that cannot be
# read out of the payload counts as outside.
_cwd_inside_this_checkout() {
    # A `case`, not `grep -q`: under pipefail an early-exiting reader can SIGPIPE
    # the writer and turn "has a cwd" into "has none".
    case "$1" in *'"cwd"'*) ;; *) return 0 ;; esac
    local cwd dir root
    cwd=$(printf '%s' "$1" | sed -n 's/.*"cwd"[[:space:]]*:[[:space:]]*"\([^"\\]*\)".*/\1/p' | sed -n 1p)
    [ -n "$cwd" ] || return 1
    dir=$(cd "$cwd" 2>/dev/null && pwd -P) || return 1
    root=$(cd "$REPO_ROOT" && pwd -P)
    case "$dir/" in "$root"/*) ;; *) return 1 ;; esac
    while [ "$dir" != "$root" ]; do
        [ -e "$dir/.git" ] && return 1
        dir=$(dirname "$dir")
    done
    return 0
}

INPUT=""
[ -t 0 ] || INPUT=$(cat)
SESSION_ROOT=""
if [ -n "$INPUT" ]; then
    SESSION_ROOT=$(printf '%s' "$INPUT" \
        | PYTHONPATH="${SHARED_DIR}" sh "$PY_LAUNCHER" -m governor.session_root_cli 2>/dev/null) || SESSION_ROOT=""
    case "$SESSION_ROOT" in
        rejected) exit 0 ;;
        none) SESSION_ROOT="" ;;
        "")
            # Plain English on purpose: this branch runs exactly when Python could
            # not, and the locale resolver below needs Python too.
            if ! _cwd_inside_this_checkout "$INPUT"; then
                echo "[stop-hook] The session's working tree could not be resolved; Stop checks skipped (#425)."
                exit 0
            fi
            ;;
    esac
fi
GIT_ROOT="${SESSION_ROOT:-$REPO_ROOT}"

# bash 3.2 (macOS default) compatible lowercase. ${var,,} is bash 4+ only.
_agent_locale_lc=""
if [ -n "${AGENT_LOCALE:-}" ]; then
    _agent_locale_lc=$(printf '%s' "$AGENT_LOCALE" | tr '[:upper:]' '[:lower:]')
fi

_resolve_locale() {
    # $1 = locale key, $2 = English fallback (caller MUST single-quote any
    # arg containing $ to avoid set -u "unbound variable" on $sync-guidelines).
    local resolved=""
    if [ -n "$_agent_locale_lc" ] && [ "$_agent_locale_lc" != "en" ]; then
        resolved=$(PYTHONPATH="$SHARED_DIR" sh "$PY_LAUNCHER" -m governor.locale "$1" 2>/dev/null) || resolved=""
    fi
    if [ -n "$resolved" ]; then
        printf '%s\n' "$resolved"
    else
        printf '%s\n' "$2"
    fi
}

# Resolve all 8 advisory strings up-front so the if/elif emit blocks stay
# straightforward. Fallbacks are single-quoted to keep $sync-guidelines /
# /sync-guidelines literal under set -u.
_SYNC_STRONG_HEADER=$(_resolve_locale SYNC_STRONG_HEADER '=== /sync-guidelines strongly recommended ===')
_SYNC_STRONG_FOOTER=$(_resolve_locale SYNC_STRONG_FOOTER '=============================================')
_SYNC_NORM_HEADER=$(_resolve_locale SYNC_NORM_HEADER '=== /sync-guidelines recommended ===')
_SYNC_NORM_FOOTER=$(_resolve_locale SYNC_NORM_FOOTER '====================================')
_SYNC_FOUNDATION_FILES_HEADER=$(_resolve_locale SYNC_FOUNDATION_FILES_HEADER 'Foundation files changed:')
_SYNC_STRUCTURE_FILES_HEADER=$(_resolve_locale SYNC_STRUCTURE_FILES_HEADER 'Domain structure files changed:')
_SYNC_CLAUDE_RUN=$(_resolve_locale SYNC_CLAUDE_RUN 'Claude: run /sync-guidelines')
_SYNC_CODEX_RUN_ALSO=$(_resolve_locale SYNC_CODEX_RUN_ALSO 'Codex: also run $sync-guidelines')

# 1) Uncommitted changes (staged + unstaged) + untracked files
UNCOMMITTED=$(git -C "$GIT_ROOT" diff --name-only HEAD 2>/dev/null || true)
UNTRACKED=$(git -C "$GIT_ROOT" ls-files --others --exclude-standard 2>/dev/null || true)
CHANGED=$(printf '%s\n%s' "$UNCOMMITTED" "$UNTRACKED" | sort -u | grep -v '^$' || true)

# 2) Fallback: working tree clean but last commit is recent (within 2h) → session commit
if [ -z "$CHANGED" ]; then
    LAST_EPOCH=$(git -C "$GIT_ROOT" log -1 --format='%ct' 2>/dev/null || echo 0)
    NOW_EPOCH=$(date +%s)
    if [ $((NOW_EPOCH - LAST_EPOCH)) -lt 7200 ]; then
        CHANGED=$(git -C "$GIT_ROOT" diff --name-only HEAD~1 HEAD 2>/dev/null || true)
    fi
fi

# Phase 4 completion-gate: marker cleanup runs on every Stop regardless of
# CHANGED (IC-11 Option A — consume exception-token markers on every Stop
# event, not only when files changed). Output captured here; printed below
# only when CHANGED is non-empty so advisory sessions stay silent.
# Fail-open: helper crash → markers not cleaned, advisory unaffected (HC-4.7).
COMPLETION_OUT=$(sh "$PY_LAUNCHER" "${HOOK_DIR}/completion_gate.py" ${SESSION_ROOT:+"$SESSION_ROOT"} 2>/dev/null || true)

# Work-ledger: refresh verification snapshot from git on every Stop (fail-open).
PYTHONPATH="${SHARED_DIR}" sh "$PY_LAUNCHER" -c "
import sys; sys.path.insert(0, '${SHARED_DIR}')
try:
    from governor import resolve_session_roots
    from work_ledger import update_verification_from_git
    roots = resolve_session_roots({'cwd': sys.argv[1]} if len(sys.argv) > 1 else {})
    if not roots.rejected:
        update_verification_from_git(repo_root=roots.repo_root, state_root=roots.state_root)
except Exception:
    pass
" ${SESSION_ROOT:+"$SESSION_ROOT"} 2>/dev/null || true

[ -z "$CHANGED" ] && exit 0

WORKFLOW_OUT=$(printf '%s\n' "$CHANGED" \
    | PYTHONPATH="${SHARED_DIR}" sh "$PY_LAUNCHER" -c '
import sys
changed = [line.strip() for line in sys.stdin.read().splitlines() if line.strip()]
governor_changing = False
try:
    from governor import resolve_session_roots
    roots = resolve_session_roots({"cwd": sys.argv[1]} if len(sys.argv) > 1 else {})
except Exception:
    roots = None
try:
    from governor import is_governor_changing, is_log_only_backfill, parse_trigger_globs
    session = roots.repo_root if roots is not None else None
    globs = parse_trigger_globs() if session is None else parse_trigger_globs(session / "docs" / "ai" / "shared" / "governor-paths.md")
    governor_changing = bool(changed) and not is_log_only_backfill(changed) and is_governor_changing(changed, globs)
except Exception:
    governor_changing = False
try:
    from work_ledger import build_workflow_advisory_segments
    if roots is None or not roots.rejected:
        segments = build_workflow_advisory_segments(changed_files=changed, governor_changing=governor_changing, state_root=roots.state_root if roots is not None else None)
        if segments:
            print("\n\n".join(segments))
except Exception:
    pass
' ${SESSION_ROOT:+"$SESSION_ROOT"} 2>/dev/null || true)

# Delegate classification to governor.sync_advisory via Python shim (F-1 SOT).
# HC-5.5 fail-open: if the shim is unavailable, fall back to inline grep patterns.
FOUNDATION=""
STRUCTURE=""
_ADVISORY_OK=0
if _ADVISORY_RAW=$(printf '%s\n' "$CHANGED" \
        | PYTHONPATH="${SHARED_DIR}" sh "$PY_LAUNCHER" -m governor.sync_advisory_cli 2>/dev/null); then
    _ADVISORY_LEVEL=$(echo "$_ADVISORY_RAW" | head -1)
    _ADVISORY_FILES=$(echo "$_ADVISORY_RAW" | tail -n +2 | grep -v '^$' || true)
    case "$_ADVISORY_LEVEL" in
        foundation) FOUNDATION="$_ADVISORY_FILES"; _ADVISORY_OK=1 ;;
        structure)  STRUCTURE="$_ADVISORY_FILES";  _ADVISORY_OK=1 ;;
        none)       _ADVISORY_OK=1 ;;
        *)          _ADVISORY_OK=1 ;;  # future extension — treat unknown level as none
    esac
fi

if [ "$_ADVISORY_OK" -eq 0 ]; then
    # Fallback: governor.sync_advisory_cli unavailable (Python absent, import error, etc.)
    FOUNDATION=$(echo "$CHANGED" | grep -E '^(src/_core/|src/_apps/|pyproject\.toml$|\.pre-commit-config\.yaml$|AGENTS\.md$|CLAUDE\.md$|\.codex/|\.antigravity/|\.gemini/|\.agents/|\.claude/rules/|\.claude/hooks/|\.claude/settings\.json$|docs/ai/shared/|docs/ai/shared/skills/)' || true)
    STRUCTURE=$(echo "$CHANGED" | grep -E '^src/[^_].*/((infrastructure/di/|interface/server/routers/|domain/protocols/|domain/dtos/))' || true)
fi

if [ -n "$FOUNDATION" ]; then
    echo ""
    echo "$_SYNC_STRONG_HEADER"
    echo "$_SYNC_FOUNDATION_FILES_HEADER"
    echo "$FOUNDATION" | sed 's/^/  - /'
    echo "$_SYNC_CLAUDE_RUN"
    echo "$_SYNC_CODEX_RUN_ALSO"
    echo "$_SYNC_STRONG_FOOTER"
elif [ -n "$STRUCTURE" ]; then
    echo ""
    echo "$_SYNC_NORM_HEADER"
    echo "$_SYNC_STRUCTURE_FILES_HEADER"
    echo "$STRUCTURE" | sed 's/^/  - /'
    echo "$_SYNC_NORM_FOOTER"
fi

if [ -n "$COMPLETION_OUT" ]; then
    echo ""
    echo "$COMPLETION_OUT"
fi

if [ -n "$WORKFLOW_OUT" ]; then
    echo ""
    echo "$WORKFLOW_OUT"
fi

exit 0
