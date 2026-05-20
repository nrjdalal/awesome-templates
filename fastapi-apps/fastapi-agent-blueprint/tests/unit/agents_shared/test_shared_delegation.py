"""Unit tests for .codex/hooks/_shared.py delegation (PR-A.6 cross-review fix).

Verifies that changed_files() correctly delegates to governor.completion_gate
when available, falls back to inline logic when not, and is exception-safe
in all paths (HC-5.5 execution fail-open).
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[3]
_HOOKS = REPO_ROOT / ".codex" / "hooks"
if str(_HOOKS) not in sys.path:
    sys.path.insert(0, str(_HOOKS))

import _shared as shared_module

# ---------------------------------------------------------------------------
# Delegation path (_GATE_OK=True)
# ---------------------------------------------------------------------------


def test_changed_files_delegates_to_impl_when_gate_ok() -> None:
    """When _GATE_OK is True and _impl is available, changed_files() calls _impl."""
    sentinel = ["AGENTS.md", ".codex/hooks/foo.py"]

    with (
        patch.object(shared_module, "_GATE_OK", True),
        patch.object(shared_module, "_impl", return_value=sentinel),
    ):
        result = shared_module.changed_files()

    assert result == sentinel


def test_changed_files_impl_exception_falls_through_to_fallback() -> None:
    """If _impl() raises, changed_files() falls through to the inline fallback (HC-5.5)."""

    def _broken():
        raise RuntimeError("git subprocess failed")

    with (
        patch.object(shared_module, "_GATE_OK", True),
        patch.object(shared_module, "_impl", side_effect=_broken),
        patch.object(
            shared_module,
            "run_command",
            side_effect=[
                type("R", (), {"stdout": "AGENTS.md\n", "returncode": 0})(),
                type("R", (), {"stdout": "", "returncode": 0})(),
            ],
        ),
    ):
        result = shared_module.changed_files()

    assert result == ["AGENTS.md"]


# ---------------------------------------------------------------------------
# Fallback path (_GATE_OK=False)
# ---------------------------------------------------------------------------


def test_changed_files_uses_fallback_when_gate_not_ok() -> None:
    """When _GATE_OK is False, changed_files() uses the inline git fallback."""
    with (
        patch.object(shared_module, "_GATE_OK", False),
        patch.object(
            shared_module,
            "run_command",
            side_effect=[
                type("R", (), {"stdout": "src/user/service.py\n", "returncode": 0})(),
                type("R", (), {"stdout": "newfile.py\n", "returncode": 0})(),
            ],
        ),
    ):
        result = shared_module.changed_files()

    assert "src/user/service.py" in result
    assert "newfile.py" in result


def test_changed_files_fallback_returns_sorted() -> None:
    """Fallback path returns a sorted list (consistent with changed_files_via_git)."""
    with (
        patch.object(shared_module, "_GATE_OK", False),
        patch.object(
            shared_module,
            "run_command",
            side_effect=[
                type("R", (), {"stdout": "z_file.py\na_file.py\n", "returncode": 0})(),
                type("R", (), {"stdout": "", "returncode": 0})(),
            ],
        ),
    ):
        result = shared_module.changed_files()

    assert result == sorted(result), "Fallback result must be sorted"


def test_changed_files_fallback_deduplicates() -> None:
    """Fallback path deduplicates files that appear in both git diff and ls-files."""
    with (
        patch.object(shared_module, "_GATE_OK", False),
        patch.object(
            shared_module,
            "run_command",
            side_effect=[
                type("R", (), {"stdout": "dup.py\n", "returncode": 0})(),
                type("R", (), {"stdout": "dup.py\n", "returncode": 0})(),
            ],
        ),
    ):
        result = shared_module.changed_files()

    assert result.count("dup.py") == 1
