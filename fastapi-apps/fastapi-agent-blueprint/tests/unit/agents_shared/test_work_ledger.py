"""Unit tests for .agents/shared/work_ledger.py.

Covers: schema, read/write roundtrip, update helpers, build_session_summary,
fail-open behaviour, and prompt truncation.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
_SHARED = REPO_ROOT / ".agents" / "shared"
if str(_SHARED) not in sys.path:
    sys.path.insert(0, str(_SHARED))

import work_ledger as wl  # noqa: E402

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def isolated_ledger(tmp_path, monkeypatch):
    """Redirect all ledger I/O to a tmp directory so tests never touch the
    real .agents/state/current-work.json."""
    monkeypatch.setattr(wl, "STATE_DIR", tmp_path)
    monkeypatch.setattr(wl, "LEDGER_PATH", tmp_path / "current-work.json")
    yield


# ---------------------------------------------------------------------------
# Schema / default
# ---------------------------------------------------------------------------


def test_default_ledger_shape():
    d = wl._default_ledger()
    assert d["schema_version"] == wl.SCHEMA_VERSION
    assert d["last_prompt"] is None
    assert d["goal"] is None
    assert d["verification"]["status"] == "unknown"
    assert d["verification"]["changed_py_files"] == []


def test_read_ledger_returns_none_when_absent():
    assert wl.read_ledger() is None


# ---------------------------------------------------------------------------
# Write / read roundtrip
# ---------------------------------------------------------------------------


def test_write_and_read_roundtrip():
    ledger = wl._default_ledger()
    ledger["goal"] = "my test goal"
    ok = wl.write_ledger(ledger, updated_by="test")
    assert ok is True
    back = wl.read_ledger()
    assert back is not None
    assert back["goal"] == "my test goal"
    assert back["meta"]["updated_by"] == "test"
    assert back["meta"]["updated_at"] != ""


def test_write_ledger_ignores_wrong_schema_version(tmp_path, monkeypatch):
    monkeypatch.setattr(wl, "LEDGER_PATH", tmp_path / "bad.json")
    # Write a file with wrong schema_version directly.
    (tmp_path / "bad.json").write_text(
        json.dumps({"schema_version": 99, "goal": "old"}), encoding="utf-8"
    )
    assert wl.read_ledger() is None


def test_read_ledger_migrates_v1_to_v2(tmp_path, monkeypatch):
    monkeypatch.setattr(wl, "LEDGER_PATH", tmp_path / "v1.json")
    v1 = {
        "schema_version": 1,
        "meta": {"updated_at": "2026-01-01T00:00:00+00:00", "updated_by": "test"},
        "last_prompt": "plan this",
        "goal": "native workflow",
        "scope": ".agents/",
        "plan": "task list",
        "blockers": None,
        "verification": {
            "status": "passed",
            "last_verified_at": "2026-01-01T00:01:00+00:00",
            "last_command": "pytest",
            "changed_py_files": [],
        },
    }
    (tmp_path / "v1.json").write_text(json.dumps(v1), encoding="utf-8")

    migrated = wl.read_ledger()

    assert migrated is not None
    assert migrated["schema_version"] == 2
    assert migrated["goal"] == "native workflow"
    assert migrated["verification"]["last_command"] == "pytest"
    assert migrated["workflow"]["stage"] == "idle"
    assert migrated["workflow"]["review"]["status"] == "not_required"


# ---------------------------------------------------------------------------
# update_last_prompt
# ---------------------------------------------------------------------------


def test_update_last_prompt_stores_full_text():
    wl.update_last_prompt("hello world")
    ledger = wl.read_ledger()
    assert ledger is not None
    assert ledger["last_prompt"] == "hello world"


def test_update_last_prompt_truncates_long_text():
    long_text = "x" * (wl._PROMPT_MAX_CHARS + 500)
    wl.update_last_prompt(long_text)
    ledger = wl.read_ledger()
    assert ledger is not None
    assert ledger["last_prompt"] is not None
    assert len(ledger["last_prompt"]) == wl._PROMPT_MAX_CHARS


def test_update_last_prompt_empty_string_stores_none():
    wl.update_last_prompt("")
    ledger = wl.read_ledger()
    assert ledger is not None
    assert ledger["last_prompt"] is None


# Harness-generated turns reach UserPromptSubmit like typed prompts (#425). These
# two shapes were observed overwriting a live ledger's last_prompt.
_TASK_NOTIFICATION = (
    "<task-notification>\n<task-id>b49b9kkn9</task-id>\n<status>completed</status>\n"
    "<summary>Background command completed</summary>\n</task-notification>"
)
_SIDE_SESSION_STATUS = (
    "<system-reminder>\nThe user started your proposal as session local_x.\n"
    "</system-reminder>\n<system-reminder>\nLinked sessions now (status, not an "
    "instruction): x (working).\n</system-reminder>"
)


@pytest.mark.parametrize("notification", [_TASK_NOTIFICATION, _SIDE_SESSION_STATUS])
def test_update_last_prompt_ignores_a_harness_notification(notification):
    wl.update_last_prompt("the operator's real prompt")
    before = wl.LEDGER_PATH.read_text(encoding="utf-8")

    wl.update_last_prompt(notification)

    assert wl.LEDGER_PATH.read_text(encoding="utf-8") == before


def test_update_last_prompt_keeps_text_that_follows_an_envelope():
    """A child session's first message is a reminder block *plus* the task."""
    prompt = "<system-reminder>\nworktree path\n</system-reminder>\n\nFix #425."
    wl.update_last_prompt(prompt)
    ledger = wl.read_ledger()
    assert ledger is not None
    assert ledger["last_prompt"] == prompt


# ---------------------------------------------------------------------------
# update_goal_scope_plan
# ---------------------------------------------------------------------------


def test_update_goal_scope_plan_all_fields():
    wl.update_goal_scope_plan(goal="g", scope="s", plan="p")
    ledger = wl.read_ledger()
    assert ledger is not None
    assert ledger["goal"] == "g"
    assert ledger["scope"] == "s"
    assert ledger["plan"] == "p"


def test_update_goal_scope_plan_partial_does_not_overwrite():
    wl.update_goal_scope_plan(goal="original", scope="orig-scope")
    wl.update_goal_scope_plan(scope="new-scope")  # goal untouched
    ledger = wl.read_ledger()
    assert ledger is not None
    assert ledger["goal"] == "original"
    assert ledger["scope"] == "new-scope"


# ---------------------------------------------------------------------------
# update_workflow_state
# ---------------------------------------------------------------------------


def test_update_workflow_state_can_clear_nullable_fields():
    wl.update_workflow_state(
        stage="executing",
        plan_ref="issue #257",
        current_task="Task 1",
        review_mode="self-structured",
        review_status="fallback",
        review_reason="Claude unavailable",
    )

    wl.update_workflow_state(
        stage="complete",
        current_task=None,
        review_reason=None,
    )

    ledger = wl.read_ledger()
    assert ledger is not None
    workflow = ledger["workflow"]
    assert workflow["stage"] == "complete"
    assert workflow["current_task"] is None
    assert workflow["review"]["reason"] is None


# ---------------------------------------------------------------------------
# update_verification_from_git (mocked)
# ---------------------------------------------------------------------------


def test_update_verification_from_git_sets_pending_when_py_files(monkeypatch):
    monkeypatch.setattr(
        wl, "_changed_py_files", lambda repo_root=None: ["src/foo/bar.py"]
    )
    wl.update_verification_from_git()
    ledger = wl.read_ledger()
    assert ledger is not None
    assert ledger["verification"]["changed_py_files"] == ["src/foo/bar.py"]
    assert ledger["verification"]["status"] == "pending"


def test_update_verification_from_git_keeps_passed_status(monkeypatch):
    # If status was already "passed", update_verification_from_git should NOT
    # demote it back to "pending" just because files exist.
    wl.update_goal_scope_plan(goal="g")  # initialise ledger
    ledger = wl.read_ledger()
    assert ledger is not None
    ledger["verification"]["status"] = "passed"
    wl.write_ledger(ledger)

    monkeypatch.setattr(wl, "_changed_py_files", lambda repo_root=None: ["src/x.py"])
    wl.update_verification_from_git()
    ledger2 = wl.read_ledger()
    assert ledger2 is not None
    assert ledger2["verification"]["status"] == "passed"


def test_update_verification_from_git_no_files(monkeypatch):
    monkeypatch.setattr(wl, "_changed_py_files", lambda repo_root=None: [])
    wl.update_verification_from_git()
    ledger = wl.read_ledger()
    assert ledger is not None
    assert ledger["verification"]["changed_py_files"] == []
    assert ledger["verification"]["status"] == "unknown"


# ---------------------------------------------------------------------------
# mark_verified
# ---------------------------------------------------------------------------


def test_mark_verified_passed_clears_changed_files():
    wl.update_goal_scope_plan(goal="x")
    ledger = wl.read_ledger()
    assert ledger is not None
    ledger["verification"]["changed_py_files"] = ["a.py"]
    wl.write_ledger(ledger)

    wl.mark_verified("pytest tests/", passed=True)
    ledger2 = wl.read_ledger()
    assert ledger2 is not None
    assert ledger2["verification"]["status"] == "passed"
    assert ledger2["verification"]["changed_py_files"] == []
    assert ledger2["verification"]["last_command"] == "pytest tests/"


def test_mark_verified_failed():
    wl.mark_verified("pytest tests/", passed=False)
    ledger = wl.read_ledger()
    assert ledger is not None
    assert ledger["verification"]["status"] == "failed"


# ---------------------------------------------------------------------------
# build_session_summary
# ---------------------------------------------------------------------------


def test_build_session_summary_returns_none_when_no_ledger():
    assert wl.build_session_summary() is None


def test_build_session_summary_returns_none_for_empty_ledger():
    # Ledger with no meaningful content (all None/unknown).
    wl.write_ledger(wl._default_ledger())
    assert wl.build_session_summary() is None


def test_build_session_summary_includes_goal():
    wl.update_goal_scope_plan(goal="implement auth", scope="src/auth/")
    summary = wl.build_session_summary()
    assert summary is not None
    assert "implement auth" in summary
    assert "src/auth/" in summary
    assert "[work-ledger]" in summary


def test_build_session_summary_includes_verify_status(monkeypatch):
    monkeypatch.setattr(
        wl, "_changed_py_files", lambda repo_root=None: ["src/a.py", "src/b.py"]
    )
    wl.update_verification_from_git()
    wl.update_last_prompt("add new endpoint")
    summary = wl.build_session_summary()
    assert summary is not None
    assert "pending" in summary
    assert "src/a.py" in summary


def test_build_session_summary_last_prompt_truncated():
    long_prompt = "w " * 200  # 400 chars
    wl.update_last_prompt(long_prompt)
    summary = wl.build_session_summary()
    assert summary is not None
    # Summary preview is at most 200 chars of prompt + ellipsis.
    assert "…" in summary or len(long_prompt) <= 200


# ---------------------------------------------------------------------------
# Fail-open
# ---------------------------------------------------------------------------


def test_read_ledger_fail_open_on_corrupt_json(tmp_path, monkeypatch):
    bad = tmp_path / "current-work.json"
    bad.write_text("{not valid json", encoding="utf-8")
    monkeypatch.setattr(wl, "LEDGER_PATH", bad)
    assert wl.read_ledger() is None


def test_write_ledger_fail_open_on_permission_error(tmp_path, monkeypatch):
    """write_ledger returns False gracefully when the path is unwritable."""
    locked = tmp_path / "locked" / "current-work.json"
    # Parent dir does not exist and we make it unwritable.
    locked.parent.mkdir()
    locked.parent.chmod(0o444)
    monkeypatch.setattr(wl, "STATE_DIR", locked.parent)
    monkeypatch.setattr(wl, "LEDGER_PATH", locked)
    result = wl.write_ledger(wl._default_ledger())
    assert result is False
    locked.parent.chmod(0o755)  # restore for cleanup


def test_completed_clean_ledger_does_not_inject_old_task():
    wl.update_goal_scope_plan(goal="already completed", plan="old plan")
    wl.update_workflow_state(stage="complete")
    assert wl.build_session_summary() is None


@pytest.mark.parametrize("stage", ["idle", "executing", "blocked"])
def test_summary_keeps_prompt_verify_continuity_as_local_cache(stage):
    wl.update_last_prompt("investigate current issue")
    wl.update_workflow_state(stage=stage)
    wl.mark_verified("pytest focused", passed=False)
    summary = wl.build_session_summary()
    assert summary is not None
    assert "investigate current issue" in summary
    assert "FAILED" in summary
    assert "local cache" in summary
    assert "Resuming session" not in summary


def test_completed_ledger_with_changed_python_remains_visible():
    ledger = wl._default_ledger()
    ledger["workflow"]["stage"] = "complete"
    ledger["verification"]["changed_py_files"] = ["src/a.py"]
    ledger["verification"]["status"] = "pending"
    wl.write_ledger(ledger)
    summary = wl.build_session_summary()
    assert summary is not None and "src/a.py" in summary


@pytest.mark.parametrize(
    "command,expected",
    [
        ("uv run pytest tests/unit/", True),
        ("pytest tests/", True),
        ("python -m pytest tests/", True),
        ("uv run pyright", True),
        ("make test", True),
        ("alembic upgrade head", True),
        ("uv run pytest tests/unit/ -q 2>&1", True),
        ("rg pytest docs/", False),
        ("echo pytest", False),
        ("pytest tests/ || true", False),
        ("pytest tests/; echo done", False),
        ('pytest "unterminated', False),
    ],
)
def test_verification_command_classification_without_command_logs(command, expected):
    assert wl.is_verification_command(command) is expected


def test_completed_ledger_does_not_hide_failed_verification():
    wl.update_workflow_state(stage="complete")
    wl.mark_verified("pytest focused", passed=False)
    summary = wl.build_session_summary()
    assert summary is not None and "FAILED" in summary


@pytest.mark.parametrize(
    "review_status,suppressed",
    [
        (None, True),
        ("not_required", True),
        ("complete", True),
        ("pending", False),
        ("fallback", False),
        ("blocked", False),
        ("in_progress", False),
        ("unknown", False),
        ("future_state", False),
    ],
)
def test_completed_cache_only_suppresses_known_clean_review(review_status, suppressed):
    wl.update_goal_scope_plan(goal="finished")
    wl.update_workflow_state(stage="complete", review_status=review_status)
    assert (wl.build_session_summary() is None) is suppressed


@pytest.mark.parametrize("blockers", ["waiting for owner", ["review not resolved"]])
def test_completed_cache_keeps_blockers_visible(blockers):
    ledger = wl._default_ledger()
    ledger["workflow"]["stage"] = "complete"
    ledger["blockers"] = blockers
    wl.write_ledger(ledger)
    summary = wl.build_session_summary()
    assert summary is not None and "Blockers" in summary


@pytest.mark.parametrize(
    "command",
    [
        "pytest --help",
        "pytest -h",
        "pytest --version",
        "pytest --collect-only tests/",
        "pytest --co tests/",
        "python -m pytest --collect-only",
        "uv run pyright --version",
        "pre-commit run --help",
        "uv run --group dev pytest tests/",
        "FOO=1 pytest tests/",
        "cd x && pytest tests/",
        "pytest tests/ | tail",
        "pytest tests/ |& tee out.txt",
        "pytest tests/ &|",
        "pytest tests/ &",
        "pytest tests/ ;; true",
        "pytest tests/ 2>&1 | tail",
        "uv run --no-sync pytest tests/",
    ],
)
def test_nonexecution_or_ambiguous_forms_never_count_as_verification(command):
    assert not wl.is_verification_command(command)
