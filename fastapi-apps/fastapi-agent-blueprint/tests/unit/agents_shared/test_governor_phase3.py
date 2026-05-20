"""Shared governor Phase 3 surface — direct unit tests.

Targets ``governor.verify`` directly. The existing
``tests/unit/agents_shared/test_verify_first.py`` continues to exercise
the hook scripts; both suites must pass throughout Phase 5 (HC-5.1).
"""

from __future__ import annotations

from governor import (
    REMINDER_TEXT,
    extract_file_path,
    is_python_source,
    should_remind_claude,
    write_marker,
)


def test_reminder_text_lines() -> None:
    """Verify-first reminder structure — frozen at Phase 3.

    Tests the *structure* of the reminder, not its exact wording. The four-
    line shape is the contract:
    line 0 — `[verify-first] ...` tagged announcement
    line 1 — guidance / suggested action
    line 2 — `Suggested next: ...` actionable next-step pointer
    line 3 — silence hint mentioning both English and Korean exception tokens

    PR #131 (Tier 1 Language Policy) translated the original Korean opening
    line to English; the bilingual `[탐색]` token in line 3 is preserved
    (token vocabulary is the only allowed exception). Wording inside lines 1
    and 2 is intentionally not asserted byte-for-byte so a synonym rewrite
    does not break the test as long as the structural contract holds.
    """

    lines = REMINDER_TEXT.splitlines()
    assert len(lines) == 4
    assert lines[0].startswith("[verify-first] ")
    # line 1 is free-form guidance — assert only that it is a non-empty,
    # Hangul-free sentence (the policy is what is enforced; exact wording is not).
    assert lines[1].strip()
    assert "Suggested next" in lines[2]
    assert "[exploration]" in lines[3] and "[탐색]" in lines[3]


def test_is_python_source_true_for_py() -> None:
    assert is_python_source("foo/bar.py") is True


def test_is_python_source_false_for_other_extensions() -> None:
    assert is_python_source("foo.md") is False
    assert is_python_source(None) is False
    assert is_python_source("") is False


def test_extract_file_path_returns_str() -> None:
    payload = {"tool_input": {"file_path": "src/foo.py"}}
    assert extract_file_path(payload) == "src/foo.py"


def test_extract_file_path_returns_none_when_missing() -> None:
    assert extract_file_path({}) is None
    assert extract_file_path({"tool_input": None}) is None
    assert extract_file_path({"tool_input": {"other": 1}}) is None


def test_extract_file_path_returns_none_for_non_string() -> None:
    payload = {"tool_input": {"file_path": 42}}
    assert extract_file_path(payload) is None


def test_should_remind_silent_on_non_python_edit(tmp_path) -> None:
    payload = {"tool_input": {"file_path": "foo.md"}}
    assert should_remind_claude(payload, tmp_path) is False


def test_should_remind_active_on_python_edit_no_marker(tmp_path) -> None:
    payload = {"tool_input": {"file_path": "src/foo.py"}}
    assert should_remind_claude(payload, tmp_path) is True


def test_should_remind_silent_on_exploration_marker(tmp_path) -> None:
    write_marker(
        {"matched": True, "token": "exploration", "rationale_required": True}, tmp_path
    )
    payload = {"tool_input": {"file_path": "src/foo.py"}}
    assert should_remind_claude(payload, tmp_path) is False


def test_should_remind_silent_on_korean_탐색_marker(tmp_path) -> None:
    write_marker(
        {"matched": True, "token": "탐색", "rationale_required": True}, tmp_path
    )
    payload = {"tool_input": {"file_path": "src/foo.py"}}
    assert should_remind_claude(payload, tmp_path) is False


def test_should_remind_active_on_trivial_marker(tmp_path) -> None:
    write_marker(
        {"matched": True, "token": "trivial", "rationale_required": True}, tmp_path
    )
    payload = {"tool_input": {"file_path": "src/foo.py"}}
    assert should_remind_claude(payload, tmp_path) is True
