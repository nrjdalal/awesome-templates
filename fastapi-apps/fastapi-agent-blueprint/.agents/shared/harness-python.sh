#!/usr/bin/env sh
# Shared Python launcher for agent harness hooks.
#
# Normal hooks fail open only when no compatible interpreter can be resolved.
# Doctor/canary mode sets HARNESS_LAUNCHER_STRICT=1 to fail hard.

MIN_PYTHON_VERSION="3.12.9"

_debug() {
    if [ "${HARNESS_DEBUG:-}" = "1" ]; then
        printf '%s\n' "[harness-python] $1" >&2
    fi
}

_fail_resolution() {
    _debug "$1"
    if [ "${HARNESS_LAUNCHER_STRICT:-}" = "1" ]; then
        printf '%s\n' "harness-python: $1" >&2
        exit 127
    fi
    exit 0
}

_absolute_script_path() {
    case "$0" in
        /*) printf '%s\n' "$0" ;;
        */*) printf '%s\n' "$(pwd)/$0" ;;
        *)
            found=$(command -v "$0" 2>/dev/null || true)
            if [ -n "$found" ]; then
                printf '%s\n' "$found"
            else
                printf '%s\n' "$0"
            fi
            ;;
    esac
}

_script_dir() {
    script_path=$(_absolute_script_path)
    dir=$(dirname "$script_path")
    (cd "$dir" 2>/dev/null && pwd -P) || return 1
}

_find_root_from_script() {
    dir=$(_script_dir) || return 1
    while [ "$dir" != "/" ] && [ -n "$dir" ]; do
        if [ -f "$dir/pyproject.toml" ] && [ -d "$dir/.agents" ]; then
            printf '%s\n' "$dir"
            return 0
        fi
        dir=$(dirname "$dir")
    done
    return 1
}

_find_root_from_git() {
    git rev-parse --show-toplevel 2>/dev/null || return 1
}

_project_root() {
    if [ -n "${HARNESS_PYTHON_REPO_ROOT:-}" ]; then
        printf '%s\n' "$HARNESS_PYTHON_REPO_ROOT"
        return 0
    fi
    _find_root_from_script && return 0
    _find_root_from_git && return 0
    return 1
}

_compatible_python() {
    "$1" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 12, 9) else 1)' >/dev/null 2>&1
}

_compatible_uv_python() {
    (cd "$REPO_ROOT" 2>/dev/null && "$1" run --no-sync python -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 12, 9) else 1)') >/dev/null 2>&1
}

REPO_ROOT=$(_project_root) || _fail_resolution "could not detect project root"

if [ -z "${HARNESS_PYTHON_DISABLE_VENV:-}" ]; then
    VENV_PYTHON=${HARNESS_PYTHON_VENV:-"$REPO_ROOT/.venv/bin/python"}
    if [ -x "$VENV_PYTHON" ] && _compatible_python "$VENV_PYTHON"; then
        cd "$REPO_ROOT" 2>/dev/null || _fail_resolution "could not enter project root"
        exec "$VENV_PYTHON" "$@"
    fi
fi

if [ -z "${HARNESS_PYTHON_DISABLE_UV:-}" ]; then
    if [ -n "${HARNESS_PYTHON_UV:-}" ]; then
        UV_BIN=$HARNESS_PYTHON_UV
    else
        UV_BIN=$(command -v uv 2>/dev/null || true)
    fi
    if [ -n "$UV_BIN" ] && _compatible_uv_python "$UV_BIN"; then
        cd "$REPO_ROOT" 2>/dev/null || _fail_resolution "could not enter project root"
        exec "$UV_BIN" run --no-sync python "$@"
    fi
fi

if [ -z "${HARNESS_PYTHON_DISABLE_SYSTEM:-}" ]; then
    SYSTEM_CANDIDATES=${HARNESS_PYTHON_SYSTEM_CANDIDATES:-"python3 python"}
    for candidate in $SYSTEM_CANDIDATES; do
        case "$candidate" in
            */*) PYTHON_BIN=$candidate ;;
            *) PYTHON_BIN=$(command -v "$candidate" 2>/dev/null || true) ;;
        esac
        if [ -n "$PYTHON_BIN" ] && [ -x "$PYTHON_BIN" ] && _compatible_python "$PYTHON_BIN"; then
            cd "$REPO_ROOT" 2>/dev/null || _fail_resolution "could not enter project root"
            exec "$PYTHON_BIN" "$@"
        fi
    done
fi

_fail_resolution "no compatible Python interpreter found (requires >=${MIN_PYTHON_VERSION})"
