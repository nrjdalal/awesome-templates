"""Shared verify-log machinery (#334).

`.claude/` did not produce the verify-log state its own tooling reads.
`tools/check_state_lifecycle.py` globs `verify-log-*.json` across every harness
state dir, and `tools/governor_state_doctor.py` reports stale counts for all
three — but only `.codex` and `.antigravity` ever wrote one, because
`append_verify_log` and `cleanup_stale_verify_logs` existed nowhere else.

The functions move here rather than being copied a third time into `.claude`.
`verify.py`'s docstring had excluded them on the grounds that they were
"session-scoped state ... only meaningful inside the Codex Stop hook"; that
stopped being true the moment a second harness needed them. What stays
harness-specific is the *session id*, which each adapter resolves itself and
passes in — so this module keeps the boundary the docstring drew, at the right
place.

Scope note: `.codex` and `.antigravity` keep their inline copies. #334 says
triplication is mandated by ADR 045 and explicitly forbids harmonising the three
trees beyond these two functions.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest
from governor.verify import (
    VERIFY_PATTERNS,
    append_verify_log,
    cleanup_stale_verify_logs,
    verify_log_path,
)

_SESSION = "session-under-test"


class TestVerifyPatterns:
    @pytest.mark.parametrize(
        "command",
        [
            "pytest tests/ -q",
            "uv run pytest tests/unit -x",
            "make test",
            "make demo",
            "make demo-rag",
            "alembic upgrade head",
        ],
    )
    def test_recognises_a_verify_command(self, command: str) -> None:
        assert any(__import__("re").search(p, command) for p in VERIFY_PATTERNS)

    @pytest.mark.parametrize(
        "command", ["ls -la", "git status", "echo make tested", "cat Makefile"]
    )
    def test_ignores_a_non_verify_command(self, command: str, tmp_path: Path) -> None:
        assert append_verify_log(command, tmp_path, _SESSION) is None
        assert list(tmp_path.glob("verify-log-*.json")) == []

    @pytest.mark.parametrize("command", ["rg pytest docs/", "grep -r pytest ."])
    def test_known_false_positive_searching_for_the_word_counts_as_running_it(
        self, command: str, tmp_path: Path
    ) -> None:
        """Documented, not desired.

        `\bpytest\b` matches a *search* for the word as readily as a run of
        it, so grepping the docs marks the verify gate satisfied. The patterns
        are byte-identical to the inline copies in `.codex` and `.antigravity`;
        tightening them here alone would break the parity ADR 045 mandates and
        that #334 explicitly protects ("do not harmonise beyond these
        functions"). Recorded so the next person finds a test rather than a
        surprise — fixing it means changing all three together.
        """
        assert append_verify_log(command, tmp_path, _SESSION) is not None


class TestAppendVerifyLog:
    def test_writes_a_jsonl_record_for_a_verify_command(self, tmp_path: Path) -> None:
        path = append_verify_log("pytest tests/ -q", tmp_path, _SESSION)

        assert path == verify_log_path(tmp_path, _SESSION)
        assert path is not None
        record = json.loads(path.read_text(encoding="utf-8").strip())
        assert record["cmd"] == "pytest tests/ -q"
        assert isinstance(record["ts_epoch_ns"], int)
        assert record["ts"].endswith("Z")

    def test_returns_none_and_writes_nothing_for_other_commands(
        self, tmp_path: Path
    ) -> None:
        assert append_verify_log("git status", tmp_path, _SESSION) is None
        assert list(tmp_path.glob("verify-log-*.json")) == []

    def test_appends_rather_than_truncating(self, tmp_path: Path) -> None:
        # Append-only is what makes this race-safe across concurrent sessions.
        append_verify_log("pytest a", tmp_path, _SESSION)
        path = append_verify_log("pytest b", tmp_path, _SESSION)

        assert path is not None
        lines = path.read_text(encoding="utf-8").strip().splitlines()
        assert [json.loads(line)["cmd"] for line in lines] == ["pytest a", "pytest b"]

    def test_creates_the_state_directory(self, tmp_path: Path) -> None:
        state_dir = tmp_path / "does-not-exist-yet"

        append_verify_log("pytest tests/", state_dir, _SESSION)

        assert state_dir.is_dir()

    def test_sessions_do_not_share_a_file(self, tmp_path: Path) -> None:
        append_verify_log("pytest a", tmp_path, "session-a")
        append_verify_log("pytest b", tmp_path, "session-b")

        assert len(list(tmp_path.glob("verify-log-*.json"))) == 2


class TestCleanupStaleVerifyLogs:
    def _aged_log(self, state_dir: Path, session: str, age_s: float) -> Path:
        path = verify_log_path(state_dir, session)
        state_dir.mkdir(parents=True, exist_ok=True)
        path.write_text("{}\n", encoding="utf-8")
        stamp = time.time() - age_s
        import os

        os.utime(path, (stamp, stamp))
        return path

    def test_deletes_another_sessions_stale_log(self, tmp_path: Path) -> None:
        stale = self._aged_log(tmp_path, "other-session", 86400 + 60)

        cleanup_stale_verify_logs(tmp_path, _SESSION)

        assert not stale.exists()

    def test_keeps_another_sessions_fresh_log(self, tmp_path: Path) -> None:
        fresh = self._aged_log(tmp_path, "other-session", 60)

        cleanup_stale_verify_logs(tmp_path, _SESSION)

        assert fresh.exists()

    def test_never_deletes_the_current_session_even_when_stale(
        self, tmp_path: Path
    ) -> None:
        # The current session's log is live state; pruning it would make the
        # Stop hook believe no verification ran in this session.
        mine = self._aged_log(tmp_path, _SESSION, 86400 * 7)

        cleanup_stale_verify_logs(tmp_path, _SESSION)

        assert mine.exists()

    def test_is_a_noop_on_a_missing_directory(self, tmp_path: Path) -> None:
        cleanup_stale_verify_logs(tmp_path / "nope", _SESSION)

    def test_leaves_unrelated_files_alone(self, tmp_path: Path) -> None:
        other = tmp_path / "exception-token-abc.json"
        tmp_path.mkdir(parents=True, exist_ok=True)
        other.write_text("{}", encoding="utf-8")
        import os

        stamp = time.time() - 86400 * 7
        os.utime(other, (stamp, stamp))

        cleanup_stale_verify_logs(tmp_path, _SESSION)

        assert other.exists()
