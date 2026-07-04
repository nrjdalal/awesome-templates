"""Phase 3 (#122) — verify-first parity tests.

Mirrors `test_token_parser.py` structure: importlib-by-path + subprocess
smokes. Covers (per plan §4.7 + R0.5 + R1.1~R1.3):
- string-equality of REMINDER_TEXT across tools (IC-2)
- silence on [exploration] / [탐색] markers (Claude AND Codex parity)
- non-silence on [trivial] / [hotfix] (escape vocabulary semantics)
- non-Python edits silent (Claude)
- Codex should_remind() marker silence (R1.3 — direct test)
- Codex verify-log freshness (recent → silent; stale → reminder)
- Codex cross-session protection via CODEX_THREAD_ID (R0.2 / R1.1)
- subsecond ordering (R0.3 — ts_epoch_ns)
- fail-open on missing state dir / corrupt marker / invalid JSON stdin
- Phase 2 marker idempotency (read does not mutate file)
- Claude emit channel (#271): hookSpecificOutput.additionalContext JSON on
  stdout, nothing on stderr, silent stdout when not reminding, ko locale
  routed through the envelope (IC-19)

Stop-hook segment merge tests are covered by manual smoke in plan §6 (the
`changed_files()` git status dependency makes pytest isolation brittle).
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import time
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
CLAUDE_PY = REPO_ROOT / ".claude" / "hooks" / "verify_first.py"
CODEX_PY = REPO_ROOT / ".codex" / "hooks" / "verify_first.py"


def _load(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def claude_helper() -> ModuleType:
    return _load("claude_verify_first", CLAUDE_PY)


@pytest.fixture(scope="module")
def codex_helper() -> ModuleType:
    # Codex helper imports `_shared` as a sibling — add the dir to sys.path.
    codex_hooks_dir = str(REPO_ROOT / ".codex" / "hooks")
    if codex_hooks_dir not in sys.path:
        sys.path.insert(0, codex_hooks_dir)
    return _load("codex_verify_first", CODEX_PY)


def _write_marker(state_dir: Path, token: str, ts: str | None = None) -> Path:
    state_dir.mkdir(parents=True, exist_ok=True)
    record = {
        "matched": True,
        "token": token,
        "rationale_required": True,
        "ts": ts or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    path = state_dir / f"exception-token-test-{token}.json"
    path.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# 1. String parity — IC-2 cornerstone
# ---------------------------------------------------------------------------
def test_reminder_text_string_equality(claude_helper, codex_helper) -> None:
    assert claude_helper.REMINDER_TEXT == codex_helper.REMINDER_TEXT


# ---------------------------------------------------------------------------
# 2~7. Claude side — should_remind() decision
# ---------------------------------------------------------------------------
def test_claude_silent_on_exploration_marker(claude_helper, tmp_path) -> None:
    _write_marker(tmp_path, "exploration")
    payload = {"tool_name": "Edit", "tool_input": {"file_path": "src/foo.py"}}
    assert claude_helper.should_remind(payload, state_dir=tmp_path) is False


def test_claude_silent_on_korean_탐색_marker(claude_helper, tmp_path) -> None:
    _write_marker(tmp_path, "탐색")
    payload = {"tool_name": "Edit", "tool_input": {"file_path": "src/foo.py"}}
    assert claude_helper.should_remind(payload, state_dir=tmp_path) is False


def test_claude_reminds_on_trivial_marker(claude_helper, tmp_path) -> None:
    _write_marker(tmp_path, "trivial")
    payload = {"tool_name": "Edit", "tool_input": {"file_path": "src/foo.py"}}
    assert claude_helper.should_remind(payload, state_dir=tmp_path) is True


def test_claude_reminds_on_hotfix_marker(claude_helper, tmp_path) -> None:
    _write_marker(tmp_path, "hotfix")
    payload = {"tool_name": "Edit", "tool_input": {"file_path": "src/foo.py"}}
    assert claude_helper.should_remind(payload, state_dir=tmp_path) is True


def test_claude_silent_on_non_python_edit(claude_helper, tmp_path) -> None:
    payload = {"tool_name": "Edit", "tool_input": {"file_path": "README.md"}}
    assert claude_helper.should_remind(payload, state_dir=tmp_path) is False


def test_claude_reminds_on_python_edit_no_marker(claude_helper, tmp_path) -> None:
    payload = {"tool_name": "Edit", "tool_input": {"file_path": "src/foo.py"}}
    assert claude_helper.should_remind(payload, state_dir=tmp_path) is True


# ---------------------------------------------------------------------------
# 8. Marker read idempotency — IC-11 contract
# ---------------------------------------------------------------------------
def test_marker_read_idempotent(claude_helper, tmp_path) -> None:
    marker = _write_marker(tmp_path, "trivial")
    before = (marker.read_text(), marker.stat().st_mtime_ns)
    _ = claude_helper.read_latest_token_marker(tmp_path)
    _ = claude_helper.read_latest_token_marker(tmp_path)
    after = (marker.read_text(), marker.stat().st_mtime_ns)
    assert before == after


# ---------------------------------------------------------------------------
# 9. Corrupt marker tolerance
# ---------------------------------------------------------------------------
def test_corrupt_marker_skipped(claude_helper, tmp_path) -> None:
    _write_marker(tmp_path, "trivial")  # current ts — passes 24h filter (Phase 4)
    bad = tmp_path / "exception-token-bad.json"
    bad.write_text("{ this is not json", encoding="utf-8")
    assert claude_helper.read_latest_token_marker(tmp_path) == "trivial"


# ---------------------------------------------------------------------------
# 10. Codex marker silence parity (R0.5 — was Claude-only originally)
# ---------------------------------------------------------------------------
def test_codex_marker_read_parity(claude_helper, codex_helper, tmp_path) -> None:
    """Both helpers' read_latest_token_marker return the same token."""
    ts_older = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - 3600))
    ts_newer = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    _write_marker(tmp_path, "exploration", ts=ts_older)
    _write_marker(tmp_path, "trivial", ts=ts_newer)
    claude_token = claude_helper.read_latest_token_marker(tmp_path)
    codex_token = codex_helper.read_latest_token_marker(tmp_path)
    assert claude_token == codex_token == "trivial"


# ---------------------------------------------------------------------------
# 11~15. Codex side — should_remind() marker silence + verify-log freshness
# ---------------------------------------------------------------------------
def test_codex_silent_when_no_python_changes(codex_helper, monkeypatch) -> None:
    monkeypatch.setattr(codex_helper, "changed_python_files", lambda: [])
    assert codex_helper.should_remind() is False


def test_codex_silent_on_exploration_marker_should_remind(
    codex_helper, monkeypatch
) -> None:
    """R1.3: Codex should_remind() directly returns False on [exploration] token."""
    monkeypatch.setattr(codex_helper, "changed_python_files", lambda: ["src/foo.py"])
    monkeypatch.setattr(
        codex_helper, "read_latest_token_marker", lambda *_: "exploration"
    )
    assert codex_helper.should_remind() is False


def test_codex_silent_on_korean_탐색_marker_should_remind(
    codex_helper, monkeypatch
) -> None:
    """R1.3: Codex should_remind() directly returns False on [탐색] token."""
    monkeypatch.setattr(codex_helper, "changed_python_files", lambda: ["src/foo.py"])
    monkeypatch.setattr(codex_helper, "read_latest_token_marker", lambda *_: "탐색")
    assert codex_helper.should_remind() is False


def test_codex_reminds_when_no_verify_log(codex_helper, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(codex_helper, "changed_python_files", lambda: ["src/foo.py"])
    monkeypatch.setattr(codex_helper, "STATE_DIR", tmp_path)
    monkeypatch.setattr(codex_helper, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(
        codex_helper, "max_changed_py_mtime_ns", lambda: 1_000_000_000_000_000_000
    )
    monkeypatch.setattr(codex_helper, "current_session_latest_verify_ns", lambda: None)
    assert codex_helper.should_remind() is True


def test_codex_should_remind_reads_token_from_configured_state_dir(
    codex_helper, tmp_path, monkeypatch
) -> None:
    state_dir = tmp_path / "isolated" / ".codex" / "state"
    seen: list[Path] = []

    def fake_read_latest_token_marker(path: Path) -> str:
        seen.append(path)
        return "exploration"

    monkeypatch.setattr(codex_helper, "changed_python_files", lambda: ["src/foo.py"])
    monkeypatch.setattr(codex_helper, "STATE_DIR", state_dir)
    monkeypatch.setattr(
        codex_helper, "read_latest_token_marker", fake_read_latest_token_marker
    )

    assert codex_helper.should_remind() is False
    assert seen == [state_dir]


def test_codex_silent_when_verify_log_recent(codex_helper, monkeypatch) -> None:
    monkeypatch.setattr(codex_helper, "changed_python_files", lambda: ["src/foo.py"])
    monkeypatch.setattr(
        codex_helper, "max_changed_py_mtime_ns", lambda: 1_000_000_000_000_000_000
    )
    monkeypatch.setattr(
        codex_helper,
        "current_session_latest_verify_ns",
        lambda: 2_000_000_000_000_000_000,
    )
    monkeypatch.setattr(codex_helper, "read_latest_token_marker", lambda *_: None)
    assert codex_helper.should_remind() is False


def test_codex_reminds_when_verify_log_older_than_py_mtime(
    codex_helper, monkeypatch
) -> None:
    """R0.5 corrected name: stale verify-log → reminder fires."""
    monkeypatch.setattr(codex_helper, "changed_python_files", lambda: ["src/foo.py"])
    monkeypatch.setattr(
        codex_helper, "max_changed_py_mtime_ns", lambda: 5_000_000_000_000_000_000
    )
    monkeypatch.setattr(
        codex_helper,
        "current_session_latest_verify_ns",
        lambda: 3_000_000_000_000_000_000,
    )
    monkeypatch.setattr(codex_helper, "read_latest_token_marker", lambda *_: None)
    assert codex_helper.should_remind() is True


# ---------------------------------------------------------------------------
# 14. Codex verify-log writer pattern recognition
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "cmd,expected",
    [
        ("pytest tests/unit", True),
        ("make test", True),
        ("make demo", True),
        ("make demo-rag", True),
        ("alembic upgrade head", True),
        ("ruff check src/", False),
        ("ls -la", False),
    ],
)
def test_codex_verify_log_writer_patterns(
    codex_helper, tmp_path, monkeypatch, cmd, expected
) -> None:
    # Force a deterministic session id via CODEX_THREAD_ID (R1.1 — preferred env var).
    monkeypatch.setenv("CODEX_THREAD_ID", "pytest-fixture")
    monkeypatch.delenv("CODEX_SESSION_ID", raising=False)
    result = codex_helper.append_verify_log(cmd, state_dir=tmp_path)
    if expected:
        assert result is not None and result.exists()
        line = result.read_text().strip().splitlines()[-1]
        record = json.loads(line)
        assert record["cmd"] == cmd
        assert isinstance(record["ts_epoch_ns"], int) and record["ts_epoch_ns"] > 0
    else:
        assert result is None


# ---------------------------------------------------------------------------
# 15. Cross-session protection (R0.2)
# ---------------------------------------------------------------------------
def test_codex_cross_session_does_not_silence(
    codex_helper, tmp_path, monkeypatch
) -> None:
    """A different session's verify-log entry must NOT silence the current session."""
    # Write a verify-log under a DIFFERENT session id.
    other_session = tmp_path / "verify-log-some-other-session.json"
    other_session.write_text(
        json.dumps(
            {
                "ts": "2026-04-27T00:00:00Z",
                "ts_epoch_ns": 9_000_000_000_000_000_000,
                "cmd": "pytest",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    # Force the current session id via CODEX_THREAD_ID (R1.1 — not matching the other file).
    monkeypatch.setenv("CODEX_THREAD_ID", "current-session")
    monkeypatch.delenv("CODEX_SESSION_ID", raising=False)
    monkeypatch.setattr(codex_helper, "STATE_DIR", tmp_path)
    # current_session_latest_verify_ns reads ONLY verify-log-{current}.json
    assert codex_helper.current_session_latest_verify_ns(state_dir=tmp_path) is None


# ---------------------------------------------------------------------------
# 16~18. Subprocess fail-open smoke (HC-3.6)
# ---------------------------------------------------------------------------
def _run_claude_verify_first(
    stdin: str, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        [sys.executable, str(CLAUDE_PY)],
        input=stdin,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


def _isolated_env(tmp_path: Path, locale: str | None = None) -> dict[str, str]:
    """Subprocess env with deterministic state dir and locale.

    ``HARNESS_STATE_ROOT`` points at ``tmp_path`` so real repo markers
    cannot silence the reminder; ``AGENT_LOCALE`` is scrubbed (or forced)
    so the expected text is deterministic.
    """
    scrub = {"AGENT_LOCALE", "HARNESS_DEBUG", "HARNESS_LAUNCHER_STRICT"}
    env = {
        k: v
        for k, v in __import__("os").environ.items()
        if k not in scrub and not k.startswith("HARNESS_PYTHON_")
    }
    env["HARNESS_STATE_ROOT"] = str(tmp_path)
    if locale is not None:
        env["AGENT_LOCALE"] = locale
    return env


def test_fail_open_empty_stdin() -> None:
    result = _run_claude_verify_first("")
    assert result.returncode == 0


def test_fail_open_invalid_json() -> None:
    result = _run_claude_verify_first("not json at all")
    assert result.returncode == 0


def test_fail_open_missing_state_dir(claude_helper, tmp_path) -> None:
    payload = {"tool_name": "Edit", "tool_input": {"file_path": "src/foo.py"}}
    # state_dir does not exist → no marker → no [exploration] silence → reminds
    assert (
        claude_helper.should_remind(payload, state_dir=tmp_path / "nonexistent") is True
    )


# ---------------------------------------------------------------------------
# 18a~18d. Claude emit channel — model-visible additionalContext JSON (#271)
# ---------------------------------------------------------------------------
# ADR 050 D3 drift-candidate remediation: plain stderr on exit 0 reaches only
# the user transcript, never the model. The reminder must be emitted as
# hookSpecificOutput.additionalContext JSON on stdout (exit 0) — the
# documented model-visible, non-blocking PostToolUse channel.
def test_claude_emits_additional_context_json_on_stdout(
    claude_helper, tmp_path
) -> None:
    payload = {"tool_name": "Edit", "tool_input": {"file_path": "src/foo.py"}}
    result = _run_claude_verify_first(json.dumps(payload), env=_isolated_env(tmp_path))
    assert result.returncode == 0
    envelope = json.loads(result.stdout)
    assert envelope["hookSpecificOutput"]["hookEventName"] == "PostToolUse"
    assert (
        envelope["hookSpecificOutput"]["additionalContext"]
        == claude_helper.REMINDER_TEXT
    )


def test_claude_reminder_not_on_stderr(tmp_path) -> None:
    """Regression for the invisible-reminder defect — stderr stays empty."""
    payload = {"tool_name": "Edit", "tool_input": {"file_path": "src/foo.py"}}
    result = _run_claude_verify_first(json.dumps(payload), env=_isolated_env(tmp_path))
    assert result.returncode == 0
    assert result.stderr.strip() == ""


def test_claude_silent_stdout_when_not_reminding(tmp_path) -> None:
    """Non-Python edit → no envelope at all (empty stdout, exit 0)."""
    payload = {"tool_name": "Edit", "tool_input": {"file_path": "README.md"}}
    result = _run_claude_verify_first(json.dumps(payload), env=_isolated_env(tmp_path))
    assert result.returncode == 0
    assert result.stdout.strip() == ""


def test_claude_emit_localizes_additional_context(claude_helper, tmp_path) -> None:
    """AGENT_LOCALE=ko routes the ko table through the JSON envelope (IC-19)."""
    payload = {"tool_name": "Edit", "tool_input": {"file_path": "src/foo.py"}}
    result = _run_claude_verify_first(
        json.dumps(payload), env=_isolated_env(tmp_path, locale="ko")
    )
    assert result.returncode == 0
    envelope = json.loads(result.stdout)
    context = envelope["hookSpecificOutput"]["additionalContext"]
    assert context  # never blank (IC-19 fallback)
    assert context != claude_helper.REMINDER_TEXT  # actually translated
    assert "[verify-first]" in context  # shared tag survives translation


# ---------------------------------------------------------------------------
# 18e~18f. Registered wrapper path — bash verify-first.sh (#271 cross-review R1)
# ---------------------------------------------------------------------------
# settings.json registers the .sh wrapper (which pipes through
# harness-python.sh), not the .py module. The delivery-channel contract is
# only real if the wrapper forwards exactly one parseable JSON document on
# stdout — launcher/wrapper noise on stdout would corrupt the envelope.
CLAUDE_SH = REPO_ROOT / ".claude" / "hooks" / "verify-first.sh"


def _run_claude_wrapper(
    stdin: str, env: dict[str, str]
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        ["bash", str(CLAUDE_SH)],
        input=stdin,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


def test_wrapper_stdout_is_single_json_envelope(claude_helper, tmp_path) -> None:
    payload = {"tool_name": "Edit", "tool_input": {"file_path": "src/foo.py"}}
    result = _run_claude_wrapper(json.dumps(payload), env=_isolated_env(tmp_path))
    assert result.returncode == 0
    assert result.stderr.strip() == ""
    envelope = json.loads(result.stdout)  # exactly one JSON document
    assert envelope["hookSpecificOutput"]["hookEventName"] == "PostToolUse"
    assert (
        envelope["hookSpecificOutput"]["additionalContext"]
        == claude_helper.REMINDER_TEXT
    )


def test_wrapper_silent_when_not_reminding(tmp_path) -> None:
    payload = {"tool_name": "Edit", "tool_input": {"file_path": "README.md"}}
    result = _run_claude_wrapper(json.dumps(payload), env=_isolated_env(tmp_path))
    assert result.returncode == 0
    assert result.stdout.strip() == ""


# ---------------------------------------------------------------------------
# 19. Codex post-tool-format.py null tool_input fail-open (R1.2 regression)
# ---------------------------------------------------------------------------
def test_codex_post_tool_format_null_tool_input_fail_open() -> None:
    """R1.2: explicit null tool_input must not raise AttributeError — exits 0."""
    codex_post_tool = REPO_ROOT / ".codex" / "hooks" / "post-tool-format.py"
    result = subprocess.run(  # noqa: S603
        [sys.executable, str(codex_post_tool)],
        input='{"tool_name": "Bash", "tool_input": null}',
        capture_output=True,
        text=True,
        check=False,
        env={**__import__("os").environ, "CODEX_THREAD_ID": "pytest-r1.2"},
    )
    assert result.returncode == 0


def test_codex_post_tool_format_marks_work_ledger_verified(tmp_path) -> None:
    """A successful verify-class Bash command should update the native ledger.

    This keeps the native workflow advisory from reporting stale
    verification-pending state after pytest / make test has actually run.
    """
    codex_post_tool = REPO_ROOT / ".codex" / "hooks" / "post-tool-format.py"
    payload = {
        "tool_name": "Bash",
        "tool_input": {"command": "pytest tests/unit/agents_shared -q"},
        "tool_response": {"exit_code": 0},
    }

    result = subprocess.run(  # noqa: S603
        [sys.executable, str(codex_post_tool)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        check=False,
        env={
            **__import__("os").environ,
            "CODEX_THREAD_ID": "pytest-ledger",
            "HARNESS_STATE_ROOT": str(tmp_path),
        },
    )

    assert result.returncode == 0, result.stderr
    ledger_path = tmp_path / ".agents" / "state" / "current-work.json"
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    assert ledger["verification"]["status"] == "passed"
    assert (
        ledger["verification"]["last_command"] == "pytest tests/unit/agents_shared -q"
    )
