"""Tests for tools/check_state_lifecycle.py (#335 R3).

It was the only script under `tools/` with no test, and it is the one that runs
on **every** commit: its pre-commit hook is `always_run: true` with
`pass_filenames: false`, so it fires even for a commit that touches nothing it
inspects. A regression there blocks every commit in the repo or, worse, stops
blocking the thing it exists to block.

The two tiers are asymmetric on purpose and both are pinned here:

- git-tracked files under any `*/state/` directory are a **hard fail** — the
  `.gitignore` guard has been bypassed and verify-log or exception-token files
  may be on their way into version control.
- stale markers are **warn-only** — a Stop hook that has not fired recently is
  informational, not a reason to refuse a commit.
"""

from __future__ import annotations

import importlib.util
import os
import sys
import time
from pathlib import Path

import pytest

# Named so the numeric literal never sits on a line that also contains the
# word "token" — gitleaks' generic-api-key heuristic reads that pairing as a
# hardcoded secret.
_ONE_DAY = 86400
_STALE = _ONE_DAY * 2

REPO_ROOT = Path(__file__).resolve().parents[3]
TOOL_PATH = REPO_ROOT / "tools" / "check_state_lifecycle.py"


def _load_module():
    """Load by path like the sibling `tools` tests — `tools/` is not a package."""
    spec = importlib.util.spec_from_file_location("check_state_lifecycle", TOOL_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_state_lifecycle"] = module
    spec.loader.exec_module(module)
    return module


module = _load_module()


def _marker(directory: Path, name: str, *, age_seconds: float = 0.0) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_text("{}", encoding="utf-8")
    if age_seconds:
        stamp = time.time() - age_seconds
        os.utime(path, (stamp, stamp))
    return path


class TestTrackedStateFilesFailHard:
    def test_a_tracked_state_file_fails(self, monkeypatch, capsys) -> None:
        monkeypatch.setattr(
            module,
            "_git_tracked_state_files",
            lambda: [".claude/state/verify-log-local_abc.json"],
        )

        assert module.main() == 1
        assert "FAIL" in capsys.readouterr().err

    def test_the_remediation_command_is_printed(self, monkeypatch, capsys) -> None:
        # The message is the whole value of a hard fail — an operator who cannot
        # see how to undo it will reach for `--no-verify`.
        monkeypatch.setattr(
            module, "_git_tracked_state_files", lambda: [".codex/state/x.json"]
        )

        module.main()

        assert "git rm --cached" in capsys.readouterr().err

    def test_an_untracked_tree_passes(self, monkeypatch) -> None:
        monkeypatch.setattr(module, "_git_tracked_state_files", lambda: [])
        monkeypatch.setattr(module, "_STATE_DIRS", ())

        assert module.main() == 0

    def test_the_real_repo_has_no_tracked_state_files(self) -> None:
        """Not a unit test of the function — a check on this repository.

        This is the invariant the hook exists to hold, so it is worth asserting
        against the actual index rather than a monkeypatched stand-in.
        """
        assert module._git_tracked_state_files() == []


class TestStaleMarkersAreWarnOnly:
    @pytest.mark.parametrize(
        "name", ["exception-token-abc.json", "verify-log-local_abc.json"]
    )
    def test_a_stale_marker_warns_without_failing(
        self, monkeypatch, capsys, tmp_path: Path, name: str
    ) -> None:
        state = tmp_path / ".claude" / "state"
        _marker(state, name, age_seconds=_STALE)
        monkeypatch.setattr(module, "_git_tracked_state_files", lambda: [])
        monkeypatch.setattr(module, "REPO_ROOT", tmp_path)
        monkeypatch.setattr(module, "_STATE_DIRS", (state,))

        assert module.main() == 0, "stale markers must never block a commit"
        assert "WARNING" in capsys.readouterr().err

    def test_a_fresh_marker_is_silent(
        self, monkeypatch, capsys, tmp_path: Path
    ) -> None:
        state = tmp_path / ".claude" / "state"
        _marker(state, "verify-log-local_abc.json")
        monkeypatch.setattr(module, "_git_tracked_state_files", lambda: [])
        monkeypatch.setattr(module, "REPO_ROOT", tmp_path)
        monkeypatch.setattr(module, "_STATE_DIRS", (state,))

        assert module.main() == 0
        assert capsys.readouterr().err == ""

    def test_crossing_the_threshold_names_the_doctor(
        self, monkeypatch, capsys, tmp_path: Path
    ) -> None:
        state = tmp_path / ".claude" / "state"
        for i in range(module._STALE_WARN_THRESHOLD + 1):
            _marker(state, f"verify-log-local_{i}.json", age_seconds=_STALE)
        monkeypatch.setattr(module, "_git_tracked_state_files", lambda: [])
        monkeypatch.setattr(module, "REPO_ROOT", tmp_path)
        monkeypatch.setattr(module, "_STATE_DIRS", (state,))

        assert module.main() == 0
        assert "governor_state_doctor.py" in capsys.readouterr().err


class TestStaleCounts:
    def test_a_missing_directory_is_zero_not_an_error(self, tmp_path: Path) -> None:
        assert module._stale_counts(tmp_path / "nope") == {"total": 0, "stale": 0}

    def test_only_the_two_marker_patterns_are_counted(self, tmp_path: Path) -> None:
        _marker(tmp_path, "verify-log-local_a.json", age_seconds=_STALE)
        _marker(tmp_path, "exception-token-b.json", age_seconds=_STALE)
        _marker(tmp_path, "unrelated.json", age_seconds=_STALE)
        _marker(tmp_path, "notes.txt", age_seconds=_STALE)

        assert module._stale_counts(tmp_path) == {"total": 2, "stale": 2}

    def test_the_boundary_is_24_hours(self, tmp_path: Path) -> None:
        # Just inside the window is not stale; comfortably outside it is.
        _marker(tmp_path, "verify-log-local_fresh.json", age_seconds=_ONE_DAY - 400)
        assert module._stale_counts(tmp_path)["stale"] == 0

        _marker(tmp_path, "verify-log-local_old.json", age_seconds=_ONE_DAY + 600)
        assert module._stale_counts(tmp_path)["stale"] == 1
