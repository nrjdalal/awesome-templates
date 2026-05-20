"""Static guards and fail-open behavioral tests for PR-A.5 + F-1.

After PR-A.5, the Codex stop-sync-reminder hook must delegate classification
logic to governor.sync_advisory rather than redeclaring FOUNDATION_PREFIXES /
STRUCTURE_MARKERS inline.

After F-1, the Claude bash hook must also delegate via governor.sync_advisory_cli
with a HC-5.5 fail-open fallback to inline grep patterns.

Codex Python hook guards:
  1. FOUNDATION_PREFIXES tuple not defined inline in the hook.
  2. STRUCTURE_MARKERS tuple not defined inline in the hook.
  3. Hook imports classify_advisory from governor.sync_advisory (not facade).
  4. No getattr(governor, ...) bypass in the hook.

Codex behavioral tests:
  5. When _SYNC_OK=False (import failed), build_segments must not emit any
     sync advisory segment (HC-5.5 fail-open — IC-19 always-fallback does
     not apply when the import itself failed).

Claude bash hook guards (F-1):
  6. Bash hook invokes governor.sync_advisory_cli (primary classification path).
  7. Bash hook retains a fail-open fallback (HC-5.5: inline grep when Python unavailable).
"""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[3]
_CODEX_HOOKS = REPO_ROOT / ".codex" / "hooks"


def _load_module(name: str, path: Path) -> types.ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def _load_codex_stop_sync() -> types.ModuleType:
    """Load stop-sync-reminder.py with the Codex _shared shim pre-installed."""
    saved_shared = sys.modules.pop("_shared", None)
    saved_mod = sys.modules.pop("_codex_stop_sync_advisory_test", None)
    try:
        _load_module("_shared", _CODEX_HOOKS / "_shared.py")
        return _load_module(
            "_codex_stop_sync_advisory_test",
            _CODEX_HOOKS / "stop-sync-reminder.py",
        )
    finally:
        for name, saved in (
            ("_shared", saved_shared),
            ("_codex_stop_sync_advisory_test", saved_mod),
        ):
            if saved is not None:
                sys.modules[name] = saved
            else:
                sys.modules.pop(name, None)


_HOOK = REPO_ROOT / ".codex" / "hooks" / "stop-sync-reminder.py"
_CLAUDE_HOOK = REPO_ROOT / ".claude" / "hooks" / "stop-sync-reminder.sh"


def _text() -> str:
    return _HOOK.read_text(encoding="utf-8")


def _bash_text() -> str:
    return _CLAUDE_HOOK.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 1. FOUNDATION_PREFIXES not defined inline
# ---------------------------------------------------------------------------


def test_no_inline_foundation_prefixes() -> None:
    text = _text()
    # Must NOT define the tuple as a local name
    assert "FOUNDATION_PREFIXES = (" not in text, (
        f"{_HOOK.name}: FOUNDATION_PREFIXES defined inline. "
        "Move to governor.sync_advisory — hook must be a thin shim."
    )


# ---------------------------------------------------------------------------
# 2. STRUCTURE_MARKERS not defined inline
# ---------------------------------------------------------------------------


def test_no_inline_structure_markers() -> None:
    text = _text()
    assert "STRUCTURE_MARKERS = (" not in text, (
        f"{_HOOK.name}: STRUCTURE_MARKERS defined inline. "
        "Move to governor.sync_advisory — hook must be a thin shim."
    )


# ---------------------------------------------------------------------------
# 3. Hook imports from governor.sync_advisory submodule
# ---------------------------------------------------------------------------


def test_imports_from_sync_advisory_submodule() -> None:
    text = _text()
    assert "from governor.sync_advisory import" in text, (
        f"{_HOOK.name}: does not import from governor.sync_advisory. "
        "Classification must delegate to the shared submodule."
    )


# ---------------------------------------------------------------------------
# 4. No getattr(governor, ...) bypass
# ---------------------------------------------------------------------------


def test_no_getattr_governor_bypass() -> None:
    text = _text()
    assert "getattr(governor," not in text, (
        f"{_HOOK.name}: getattr(governor, ...) pattern detected. "
        "Use explicit submodule imports instead."
    )


# ---------------------------------------------------------------------------
# 5. Fail-open: _SYNC_OK=False → no sync advisory segment (HC-5.5)
# ---------------------------------------------------------------------------


def test_sync_ok_false_no_advisory_segment() -> None:
    """When _SYNC_OK is False, build_segments must not emit a sync advisory.

    Simulates the HC-5.5 path where governor.sync_advisory failed to import.
    build_segments must still return without error (fail-open), but the
    advisory text must be absent from all returned segments.
    """
    m = _load_codex_stop_sync()
    with (
        patch.object(m, "_SYNC_OK", False),
        patch.object(m, "_classify_advisory", None),
    ):
        segments = m.build_segments(changed=["src/_core/x.py"])

    advisory_markers = (
        "Guideline sync required before closing this work.",
        "Foundation files changed:",
        "Guideline sync recommended.",
        "Domain structure files changed:",
    )
    for seg in segments:
        for marker in advisory_markers:
            assert marker not in seg, (
                f"Sync advisory appeared despite _SYNC_OK=False: {marker!r} found in segment"
            )


# ---------------------------------------------------------------------------
# 6. Claude bash hook delegates to governor.sync_advisory_cli (F-1)
# ---------------------------------------------------------------------------


def test_claude_bash_hook_delegates_to_sync_advisory_cli() -> None:
    """stop-sync-reminder.sh must invoke governor.sync_advisory_cli (F-1 primary path)."""
    text = _bash_text()
    assert "sync_advisory_cli" in text, (
        f"{_CLAUDE_HOOK.name}: does not invoke governor.sync_advisory_cli. "
        "F-1 migration: primary classification must delegate to the shared governor module."
    )


# ---------------------------------------------------------------------------
# 7. Claude bash hook retains fail-open fallback (HC-5.5)
# ---------------------------------------------------------------------------


def test_claude_bash_hook_has_fail_open_fallback() -> None:
    """stop-sync-reminder.sh must retain the inline grep fallback for HC-5.5 compliance."""
    text = _bash_text()
    assert "_ADVISORY_OK" in text, (
        f"{_CLAUDE_HOOK.name}: _ADVISORY_OK flag absent — HC-5.5 fail-open fallback "
        "must be present so classification degrades gracefully when Python is unavailable."
    )
    # The inline grep fallback patterns must still be present in the file so the
    # hook remains functional when Python is entirely unavailable.
    assert "grep -E" in text, (
        f"{_CLAUDE_HOOK.name}: inline grep -E fallback patterns absent. "
        "HC-5.5 requires a working fallback when Python is unavailable."
    )
