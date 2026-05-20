"""Shared governor Phase 4 surface — direct unit tests.

Targets ``governor.completion_gate`` directly. The existing
``tests/unit/agents_shared/test_completion_gate.py`` continues to
exercise the hook scripts; both suites must pass throughout Phase 5
(HC-5.1).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from governor import (
    GOVERNOR_REMINDER_NO_PR,
    GOVERNOR_REMINDER_WITH_PR,
    GateResult,
    evaluate_gate,
    governor_changing_segment,
    is_governor_changing,
    is_log_only_backfill,
    match_log_entry,
    parse_trigger_globs,
    render_reminder,
    write_marker,
)


# ---------------------------------------------------------------------------
# Building blocks — log-only / governor-changing / match_log_entry
# ---------------------------------------------------------------------------
def test_is_log_only_backfill_all_under_log_dir() -> None:
    changed = [
        "docs/history/archive/governor-review-log/pr-128-foo.md",
        "docs/history/archive/governor-review-log/README.md",
    ]
    assert is_log_only_backfill(changed) is True


def test_is_log_only_backfill_mixed_returns_false() -> None:
    changed = [
        "docs/history/archive/governor-review-log/pr-128-foo.md",
        "AGENTS.md",
    ]
    assert is_log_only_backfill(changed) is False


def test_is_log_only_backfill_empty_returns_false() -> None:
    assert is_log_only_backfill([]) is False


def test_is_governor_changing_with_agents_md() -> None:
    globs = ["AGENTS.md", ".claude/**", ".codex/**"]
    assert is_governor_changing(["AGENTS.md"], globs) is True


def test_is_governor_changing_negative() -> None:
    globs = ["AGENTS.md", ".claude/**"]
    assert is_governor_changing(["src/foo/domain/bar.py"], globs) is False


@pytest.mark.parametrize(
    "changed,pr,expected",
    [
        (["docs/history/archive/governor-review-log/pr-100-foo.md"], 100, "match"),
        (["docs/history/archive/governor-review-log/pr-99-foo.md"], 100, "mismatch"),
        (["AGENTS.md"], 100, "missing"),
        (["docs/history/archive/governor-review-log/pr-100-foo.md"], None, "unknown"),
    ],
)
def test_match_log_entry(changed: list[str], pr: int | None, expected: str) -> None:
    assert match_log_entry(changed, pr) == expected


def test_parse_trigger_globs_returns_globs() -> None:
    """Loads the real governor-paths.md so any IC-10 drift surfaces here."""

    globs = parse_trigger_globs()
    assert "AGENTS.md" in globs
    assert any(g.endswith("/**") for g in globs)


# ---------------------------------------------------------------------------
# evaluate_gate — branches
# ---------------------------------------------------------------------------
def test_evaluate_gate_silent_no_changes(tmp_path) -> None:
    result = evaluate_gate(state_dir=tmp_path, changed_files=[], pr_number=None)
    assert result == GateResult("silent_no_changes", False, None)


def test_evaluate_gate_silent_log_only(tmp_path) -> None:
    changed = ["docs/history/archive/governor-review-log/pr-1-x.md"]
    result = evaluate_gate(state_dir=tmp_path, changed_files=changed, pr_number=None)
    assert result.status == "silent_log_only"
    assert result.governor_changing is False


def test_evaluate_gate_silent_exploration_marker(tmp_path) -> None:
    write_marker(
        {"matched": True, "token": "exploration", "rationale_required": True}, tmp_path
    )
    changed = ["AGENTS.md"]
    result = evaluate_gate(state_dir=tmp_path, changed_files=changed, pr_number=128)
    assert result.status == "silent_exploration"


def test_evaluate_gate_silent_not_governor(tmp_path) -> None:
    changed = ["src/foo/domain/bar.py"]
    result = evaluate_gate(state_dir=tmp_path, changed_files=changed, pr_number=None)
    assert result.status == "silent_not_governor"
    assert result.governor_changing is False


def test_evaluate_gate_match_with_pr(tmp_path) -> None:
    changed = [
        "AGENTS.md",
        "docs/history/archive/governor-review-log/pr-128-shared-governor-module.md",
    ]
    result = evaluate_gate(state_dir=tmp_path, changed_files=changed, pr_number=128)
    assert result.status == "match"
    assert result.governor_changing is True


def test_evaluate_gate_missing_with_pr(tmp_path) -> None:
    changed = ["AGENTS.md"]
    result = evaluate_gate(state_dir=tmp_path, changed_files=changed, pr_number=128)
    assert result.status == "missing"
    assert result.governor_changing is True


def test_evaluate_gate_mismatch_with_pr(tmp_path) -> None:
    changed = [
        "AGENTS.md",
        "docs/history/archive/governor-review-log/pr-99-other.md",
    ]
    result = evaluate_gate(state_dir=tmp_path, changed_files=changed, pr_number=128)
    assert result.status == "mismatch"
    assert result.governor_changing is True


def test_evaluate_gate_unknown_pr(tmp_path) -> None:
    changed = [
        "AGENTS.md",
        "docs/history/archive/governor-review-log/pr-128-x.md",
    ]
    result = evaluate_gate(state_dir=tmp_path, changed_files=changed, pr_number=None)
    assert result.status == "unknown"


# ---------------------------------------------------------------------------
# render_reminder — silent statuses + text shape
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "status",
    [
        "silent_no_changes",
        "silent_log_only",
        "silent_exploration",
        "silent_not_governor",
        "match",
        "unknown",
    ],
)
def test_render_reminder_silent_for_silent_or_match(status: str) -> None:
    governor_changing = status in ("match", "unknown")
    result = GateResult(status, governor_changing, 128)
    assert render_reminder(result) is None


def test_render_reminder_with_pr_format() -> None:
    result = GateResult("missing", True, 128)
    text = render_reminder(result)
    assert text == GOVERNOR_REMINDER_WITH_PR.format(pr=128)
    assert "PR #128" in text


def test_render_reminder_no_pr_format() -> None:
    result = GateResult("missing", True, None)
    text = render_reminder(result)
    assert text == GOVERNOR_REMINDER_NO_PR
    assert "PR number unknown" in text


def test_render_reminder_mismatch_with_pr() -> None:
    result = GateResult("mismatch", True, 99)
    text = render_reminder(result)
    assert text == GOVERNOR_REMINDER_WITH_PR.format(pr=99)


# ---------------------------------------------------------------------------
# governor_changing_segment — wrapper behaviour
# ---------------------------------------------------------------------------
def test_governor_changing_segment_wraps_evaluate_and_render(tmp_path) -> None:
    changed = ["AGENTS.md"]
    text = governor_changing_segment(
        state_dir=tmp_path, changed_files=changed, pr_number=128
    )
    assert text is not None
    assert "PR #128" in text


def test_governor_changing_segment_silent_when_log_only(tmp_path) -> None:
    changed = ["docs/history/archive/governor-review-log/pr-128-foo.md"]
    assert (
        governor_changing_segment(
            state_dir=tmp_path, changed_files=changed, pr_number=128
        )
        is None
    )


def test_governor_changing_segment_uses_md_path(tmp_path) -> None:
    """When custom md_path returns no globs, gate goes silent_not_governor."""

    empty_md = tmp_path / "empty-paths.md"
    empty_md.write_text("# no Tier sections\n", encoding="utf-8")
    text = governor_changing_segment(
        state_dir=tmp_path,
        changed_files=["AGENTS.md"],
        pr_number=128,
        md_path=empty_md,
    )
    assert text is None


def test_hooks_import_shared_reminder_constants() -> None:
    """Post commit-5: both hook shims must import GOVERNOR_REMINDER_* from
    the shared module rather than redeclaring the literals inline. This
    closes the inline-redeclaration loophole that R0-C.3 flagged."""

    repo_root = Path(__file__).resolve().parents[3]
    claude_text = (repo_root / ".claude" / "hooks" / "completion_gate.py").read_text(
        encoding="utf-8"
    )
    codex_text = (repo_root / ".codex" / "hooks" / "completion_gate.py").read_text(
        encoding="utf-8"
    )
    # Each shim imports from the shared module.
    assert "GOVERNOR_REMINDER_WITH_PR" in claude_text
    assert "GOVERNOR_REMINDER_NO_PR" in claude_text
    assert "GOVERNOR_REMINDER_WITH_PR" in codex_text
    assert "GOVERNOR_REMINDER_NO_PR" in codex_text
    assert "from governor" in claude_text
    assert "from governor" in codex_text
    # Shared constant still carries the canonical reminder line.
    # ADR 047 D2 retargets the reminder from the per-PR governor-review-log
    # archive to the PR-description Governor Footer block; the line below is
    # the canonical post-ADR-047 wording. The inline-redeclaration ban remains
    # language-agnostic.
    assert (
        "PR #{pr} description must contain a `## Governor Footer` block."
        in GOVERNOR_REMINDER_WITH_PR
    )
    # Inline redeclaration of the canonical line MUST NOT exist in shims.
    assert (
        claude_text.count(
            "PR #{pr} description must contain a `## Governor Footer` block."
        )
        == 0
    )
    assert (
        codex_text.count(
            "PR #{pr} description must contain a `## Governor Footer` block."
        )
        == 0
    )
