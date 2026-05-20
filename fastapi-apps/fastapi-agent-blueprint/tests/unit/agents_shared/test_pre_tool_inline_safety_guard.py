"""Static guards for PR-A.4 thin-shim refactor.

After PR-A.4, both pre-tool security hooks must delegate all pattern logic
to the shared governor submodules rather than redeclaring inline regexes.
These tests enforce the boundary so accidental regression is caught at CI time.

Guards:
  1. No re.compile() in either hook (patterns live in governor submodules).
  2. No SQL keyword regex pattern in either hook (delegated to code_safety.py).
  3. Hooks import from governor submodules, not from the governor facade.
  4. No getattr(governor, ...) bypass in either hook.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]

PRE_TOOL_HOOKS = [
    REPO_ROOT / ".codex" / "hooks" / "pre-tool-security.py",
    REPO_ROOT / ".claude" / "hooks" / "pre_tool_security.py",
]


def _text(hook: Path) -> str:
    return hook.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 1. No re.compile() in hook bodies
# ---------------------------------------------------------------------------


def test_no_re_compile_in_codex_pre_tool_hook() -> None:
    hook = REPO_ROOT / ".codex" / "hooks" / "pre-tool-security.py"
    assert "re.compile(" not in _text(hook), (
        f"{hook.name}: contains re.compile() — move patterns to governor.shell_safety."
    )


def test_no_re_compile_in_claude_pre_tool_hook() -> None:
    hook = REPO_ROOT / ".claude" / "hooks" / "pre_tool_security.py"
    assert "re.compile(" not in _text(hook), (
        f"{hook.name}: contains re.compile() — move patterns to governor.code_safety."
    )


# ---------------------------------------------------------------------------
# 2. No inline SQL keyword regex pattern in either hook
# ---------------------------------------------------------------------------

_SQL_PATTERN_SIGNALS = [
    # Signals that the hook is redeclaring SQL detection inline.
    "SELECT|INSERT",
    "INSERT|UPDATE",
    "UPDATE|DELETE",
]


def test_no_inline_sql_patterns_in_pre_tool_hooks() -> None:
    for hook in PRE_TOOL_HOOKS:
        text = _text(hook)
        for signal in _SQL_PATTERN_SIGNALS:
            assert signal not in text, (
                f"{hook.name}: inline SQL keyword pattern {signal!r} detected. "
                "SQL injection checks must live in governor.code_safety — "
                "the hook is a thin shim only."
            )


# ---------------------------------------------------------------------------
# 3. Hooks import from submodules, not from the governor facade
#    (from governor import check_bash_command is forbidden — must use
#     from governor.shell_safety import check_bash_command)
# ---------------------------------------------------------------------------

_FORBIDDEN_FACADE_SYMBOLS = [
    "check_bash_command",
    "check_code_safety",
]


def test_no_facade_import_in_pre_tool_hooks() -> None:
    for hook in PRE_TOOL_HOOKS:
        text = _text(hook)
        for sym in _FORBIDDEN_FACADE_SYMBOLS:
            # Allowed: "from governor.<submodule> import <sym>"
            # Forbidden: "from governor import <sym>"
            forbidden = f"from governor import {sym}"
            assert forbidden not in text, (
                f"{hook.name}: direct facade import 'from governor import {sym}' "
                "detected. Import from the submodule directly: "
                "from governor.shell_safety / governor.code_safety import ..."
            )


# ---------------------------------------------------------------------------
# 4. No getattr(governor, ...) bypass
# ---------------------------------------------------------------------------


def test_no_getattr_governor_bypass_in_pre_tool_hooks() -> None:
    for hook in PRE_TOOL_HOOKS:
        text = _text(hook)
        assert "getattr(governor," not in text, (
            f"{hook.name}: getattr(governor, ...) pattern detected. "
            "Use explicit submodule imports instead."
        )
