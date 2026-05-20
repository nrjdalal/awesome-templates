"""Regression guards for PR-A.2b: Claude Stop hook marker cleanup ordering.

Root cause (found via PR-A.1 acceptance gate):
    .claude/hooks/stop-sync-reminder.sh had `[ -z "$CHANGED" ] && exit 0`
    BEFORE the `completion_gate.py` invocation, so exception-token markers
    were never consumed when a session ended without file changes.

These tests are static (AST/text-scan) and do not spawn a subprocess, so
they run in any environment without PYTHONPATH or bash dependencies.

Two guards:
    1. ORDER GUARD — completion_gate.py call must appear before the
       `exit 0` early-exit line in stop-sync-reminder.sh
    2. PARITY GUARD — Codex stop-sync-reminder.py must call
       consume_phase2_markers unconditionally (no early-exit guard around
       it matching the old Claude pattern)
"""

from __future__ import annotations

import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_CLAUDE_STOP_HOOK = _REPO_ROOT / ".claude" / "hooks" / "stop-sync-reminder.sh"
_CODEX_STOP_HOOK = _REPO_ROOT / ".codex" / "hooks" / "stop-sync-reminder.py"

# The exact pattern that caused the bug: completion_gate call AFTER the
# early-exit guard.  Matching this means the bug has been reintroduced.
_BUG_PATTERN = re.compile(
    r"\[\s*-z\s*\"\$CHANGED\"\s*\]\s*&&\s*exit\s+0"
    r".*?"  # any content (including newlines)
    r"completion_gate\.py",
    re.DOTALL,
)


# ---------------------------------------------------------------------------
# Guard 1 — order: COMPLETION_OUT before [ -z "$CHANGED" ] && exit 0
# ---------------------------------------------------------------------------


def test_claude_stop_hook_completion_gate_before_early_exit() -> None:
    """completion_gate.py must be invoked BEFORE the early-exit guard."""
    assert _CLAUDE_STOP_HOOK.exists(), f"Hook not found: {_CLAUDE_STOP_HOOK}"
    script = _CLAUDE_STOP_HOOK.read_text(encoding="utf-8")

    # Find positions of the two critical lines.
    completion_gate_match = re.search(r"completion_gate\.py", script)
    early_exit_match = re.search(r'\[\s*-z\s*"\$CHANGED"\s*\]\s*&&\s*exit\s+0', script)

    assert completion_gate_match is not None, (
        "completion_gate.py reference not found in stop-sync-reminder.sh"
    )
    assert early_exit_match is not None, (
        "early-exit guard '[ -z \"$CHANGED\" ] && exit 0' not found in stop-sync-reminder.sh"
    )

    cg_pos = completion_gate_match.start()
    exit_pos = early_exit_match.start()

    assert cg_pos < exit_pos, (
        f"BUG REINTRODUCED: completion_gate.py (pos={cg_pos}) appears AFTER "
        f"the early-exit guard (pos={exit_pos}). "
        "This means markers are not cleaned when a session ends with no file changes. "
        "Move the COMPLETION_OUT=$(python3 .../completion_gate.py) call before "
        "'[ -z \"$CHANGED\" ] && exit 0'."
    )


def test_claude_stop_hook_bug_pattern_absent() -> None:
    """The specific bug pattern (exit before completion_gate) must be absent."""
    assert _CLAUDE_STOP_HOOK.exists(), f"Hook not found: {_CLAUDE_STOP_HOOK}"
    script = _CLAUDE_STOP_HOOK.read_text(encoding="utf-8")
    assert not _BUG_PATTERN.search(script), (
        "The early-exit-before-completion_gate bug has been reintroduced. "
        "See PR-A.2b for the fix rationale."
    )


# ---------------------------------------------------------------------------
# Guard 2 — Codex parity: consume_phase2_markers not guarded by early exit
# ---------------------------------------------------------------------------


def test_codex_stop_hook_consume_not_guarded_by_changed_check() -> None:
    """Codex stop hook must not gate consume_phase2_markers on a CHANGED equivalent."""
    assert _CODEX_STOP_HOOK.exists(), f"Hook not found: {_CODEX_STOP_HOOK}"
    source = _CODEX_STOP_HOOK.read_text(encoding="utf-8")

    # consume_phase2_markers must be present
    assert "consume_phase2_markers" in source, (
        "consume_phase2_markers not found in Codex stop-sync-reminder.py"
    )

    # The Codex hook must not have an early-return that skips cleanup based
    # on changed files.  We check that consume_phase2_markers is inside
    # main() and not inside an `if changed_files` branch.
    #
    # Simple heuristic: ensure consume_phase2_markers is NOT preceded (within
    # 5 lines) by a `if` that mentions `changed` or `CHANGED`.
    lines = source.splitlines()
    for i, line in enumerate(lines):
        if "consume_phase2_markers" in line:
            context = lines[max(0, i - 5) : i]
            for ctx_line in context:
                stripped = ctx_line.strip()
                if stripped.startswith("if ") and (
                    "changed" in stripped.lower() or "CHANGED" in stripped
                ):
                    raise AssertionError(
                        f"consume_phase2_markers at line {i + 1} appears to be "
                        f"guarded by a changed-files check: {stripped!r}. "
                        "This could cause the same accumulation bug as the Claude hook."
                    )


# ---------------------------------------------------------------------------
# Sanity: hook files have not been deleted or renamed
# ---------------------------------------------------------------------------


def test_both_stop_hooks_exist() -> None:
    assert _CLAUDE_STOP_HOOK.exists(), f"Claude Stop hook missing: {_CLAUDE_STOP_HOOK}"
    assert _CODEX_STOP_HOOK.exists(), f"Codex Stop hook missing: {_CODEX_STOP_HOOK}"
