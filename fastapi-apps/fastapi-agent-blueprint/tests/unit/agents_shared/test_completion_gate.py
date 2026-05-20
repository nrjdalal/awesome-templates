"""Phase 4 (#123) — completion-gate parity tests.

Covers (per plan §4.6):
- parse_trigger_globs: Tier A/B/C extraction from real governor-paths.md
- is_governor_changing: AGENTS.md → True; src/ → False; log-only → False (exclusion)
- match_log_entry: match / mismatch / missing / unknown cases
- pr_number_from_branch: gh success / failure / no-PR — all fail-open
- 4 sample runs from migration-strategy.md §Phase 4 acceptance criteria
- IC-11 lifecycle: consume_phase2_markers deletes files; 24h filter ignores stale
- cleanup_stale_verify_logs: other-session stale logs deleted; current session preserved
- IC-2 string-equality: Claude / Codex GOVERNOR_REMINDER_* constants identical
- Fail-open smokes: governor-paths.md absent, gh absent, state_dir absent
"""

from __future__ import annotations

import importlib.util
import json
import sys
import time
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
CLAUDE_PY = REPO_ROOT / ".claude" / "hooks" / "completion_gate.py"
CODEX_PY = REPO_ROOT / ".codex" / "hooks" / "completion_gate.py"


def _load(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def claude_gate() -> ModuleType:
    return _load("claude_completion_gate", CLAUDE_PY)


@pytest.fixture(scope="module")
def codex_gate() -> ModuleType:
    codex_hooks_dir = str(REPO_ROOT / ".codex" / "hooks")
    if codex_hooks_dir not in sys.path:
        sys.path.insert(0, codex_hooks_dir)
    return _load("codex_completion_gate", CODEX_PY)


def _fresh_ts(offset_s: int = 0) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + offset_s))


def _write_marker(state_dir: Path, token: str, ts: str | None = None) -> Path:
    state_dir.mkdir(parents=True, exist_ok=True)
    record = {
        "matched": True,
        "token": token,
        "rationale_required": True,
        "ts": ts or _fresh_ts(),
    }
    path = state_dir / f"exception-token-{token}.json"
    path.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# IC-2 string-equality
# ---------------------------------------------------------------------------
def test_governor_reminder_with_pr_string_equality(claude_gate, codex_gate) -> None:
    assert claude_gate.GOVERNOR_REMINDER_WITH_PR == codex_gate.GOVERNOR_REMINDER_WITH_PR


def test_governor_reminder_no_pr_string_equality(claude_gate, codex_gate) -> None:
    assert claude_gate.GOVERNOR_REMINDER_NO_PR == codex_gate.GOVERNOR_REMINDER_NO_PR


# ---------------------------------------------------------------------------
# parse_trigger_globs — real governor-paths.md
# ---------------------------------------------------------------------------
def test_parse_trigger_globs_returns_globs(codex_gate) -> None:
    globs = codex_gate.parse_trigger_globs()
    assert len(globs) >= 9  # Tier A(6) + Tier B(3) minimum
    assert "AGENTS.md" in globs
    assert "docs/ai/shared/**" in globs
    assert ".claude/**" in globs
    assert ".codex/**" in globs
    assert ".agents/**" in globs


def test_parse_trigger_globs_absent_file(codex_gate, tmp_path) -> None:
    result = codex_gate.parse_trigger_globs(tmp_path / "nonexistent.md")
    assert result == []


# ---------------------------------------------------------------------------
# is_governor_changing
# ---------------------------------------------------------------------------
def test_agents_md_is_governor_changing(codex_gate) -> None:
    globs = codex_gate.parse_trigger_globs()
    assert codex_gate.is_governor_changing(["AGENTS.md"], globs) is True


def test_src_py_not_governor_changing(codex_gate) -> None:
    globs = codex_gate.parse_trigger_globs()
    assert (
        codex_gate.is_governor_changing(
            ["src/user/domain/services/user_service.py"], globs
        )
        is False
    )


def test_shared_doc_is_governor_changing(codex_gate) -> None:
    globs = codex_gate.parse_trigger_globs()
    assert (
        codex_gate.is_governor_changing(["docs/ai/shared/project-dna.md"], globs)
        is True
    )


def test_claude_hook_is_governor_changing(codex_gate) -> None:
    globs = codex_gate.parse_trigger_globs()
    assert (
        codex_gate.is_governor_changing([".claude/hooks/verify_first.py"], globs)
        is True
    )


# ---------------------------------------------------------------------------
# is_log_only_backfill
# ---------------------------------------------------------------------------
def test_log_only_backfill_all_under_log_dir(codex_gate) -> None:
    changed = ["docs/history/archive/governor-review-log/pr-127-verify-first.md"]
    assert codex_gate.is_log_only_backfill(changed) is True


def test_log_only_backfill_mixed_files_not_excluded(codex_gate) -> None:
    changed = [
        "docs/history/archive/governor-review-log/pr-127-verify-first.md",
        "AGENTS.md",
    ]
    assert codex_gate.is_log_only_backfill(changed) is False


def test_log_only_backfill_rejects_pre_relocation_path(codex_gate) -> None:
    """Regression guard for #160: after the archive moved to
    docs/history/archive/, a PR editing the pre-relocation path is NOT a
    log-only backfill — that path no longer exists in tree, and treating
    it as a backfill would silence governor-changing reminders for any
    accidental resurrection of the old layout. Codex round-1 R6."""

    changed = ["docs/ai/shared/governor-review-log/pr-99-foo.md"]
    assert codex_gate.is_log_only_backfill(changed) is False


# ---------------------------------------------------------------------------
# match_log_entry
# ---------------------------------------------------------------------------
def test_match_log_entry_match(codex_gate) -> None:
    assert (
        codex_gate.match_log_entry(
            ["docs/history/archive/governor-review-log/pr-128-completion-gate.md"], 128
        )
        == "match"
    )


def test_match_log_entry_mismatch(codex_gate) -> None:
    assert (
        codex_gate.match_log_entry(
            ["docs/history/archive/governor-review-log/pr-99-old.md"], 128
        )
        == "mismatch"
    )


def test_match_log_entry_missing(codex_gate) -> None:
    assert codex_gate.match_log_entry(["AGENTS.md"], 128) == "missing"


def test_match_log_entry_unknown_no_pr(codex_gate) -> None:
    assert (
        codex_gate.match_log_entry(
            ["docs/history/archive/governor-review-log/pr-99-old.md"], None
        )
        == "unknown"
    )


def test_match_log_entry_missing_no_pr(codex_gate) -> None:
    assert codex_gate.match_log_entry(["AGENTS.md"], None) == "missing"


def test_match_log_entry_rejects_pre_relocation_path(codex_gate) -> None:
    """Codex round-2 R1: the pre-#160 location must not be treated as a
    matching log entry. If someone accidentally resurrects
    ``docs/ai/shared/governor-review-log/pr-{N}-foo.md`` for the current
    PR, ``match_log_entry`` must return ``missing`` so the completion
    gate emits its reminder instead of falsely silencing it."""

    changed = ["docs/ai/shared/governor-review-log/pr-160-foo.md"]
    assert codex_gate.match_log_entry(changed, 160) == "missing"


def test_evaluate_gate_resurrection_does_not_silence(codex_gate, monkeypatch) -> None:
    """Codex round-2 R1 (end-to-end): when only the pre-#160 path is
    edited, the gate must NOT silence as ``match`` — the file is no longer
    a recognised governor-review-log entry, so the gate keeps
    governor-changing reminders active."""

    monkeypatch.setattr(
        codex_gate,
        "changed_files",
        lambda: [
            "AGENTS.md",
            "docs/ai/shared/governor-review-log/pr-160-foo.md",
        ],
    )
    monkeypatch.setattr(codex_gate, "pr_number_from_branch", lambda: 160)
    monkeypatch.setattr(codex_gate, "_read_latest_token", lambda _: None)
    seg = codex_gate.governor_changing_segment()
    assert seg is not None
    assert "160" in seg


# ---------------------------------------------------------------------------
# pr_number_from_branch — fail-open (gh not present or no PR)
# ---------------------------------------------------------------------------
def test_pr_number_fail_open_returns_none_or_int(codex_gate) -> None:
    result = codex_gate.pr_number_from_branch()
    assert result is None or isinstance(result, int)


# ---------------------------------------------------------------------------
# 4 sample runs (migration-strategy.md §Phase 4 acceptance criteria)
# ---------------------------------------------------------------------------
def test_sample_run_1_agents_md_no_entry_reminds(codex_gate, monkeypatch) -> None:
    """(1) AGENTS.md edited, no log entry → reminder fires."""
    monkeypatch.setattr(codex_gate, "changed_files", lambda: ["AGENTS.md"])
    monkeypatch.setattr(codex_gate, "pr_number_from_branch", lambda: 128)
    monkeypatch.setattr(codex_gate, "_read_latest_token", lambda _: None)
    seg = codex_gate.governor_changing_segment()
    assert seg is not None
    assert "128" in seg


def test_sample_run_2_agents_md_matching_entry_silent(codex_gate, monkeypatch) -> None:
    """(2) AGENTS.md + matching log entry → silent."""
    monkeypatch.setattr(
        codex_gate,
        "changed_files",
        lambda: [
            "AGENTS.md",
            "docs/history/archive/governor-review-log/pr-128-completion-gate.md",
        ],
    )
    monkeypatch.setattr(codex_gate, "pr_number_from_branch", lambda: 128)
    monkeypatch.setattr(codex_gate, "_read_latest_token", lambda _: None)
    seg = codex_gate.governor_changing_segment()
    assert seg is None


def test_sample_run_3_log_only_backfill_silent(codex_gate, monkeypatch) -> None:
    """(3) Only governor-review-log/pr-100-*.md changed → silent (HC-4.5)."""
    monkeypatch.setattr(
        codex_gate,
        "changed_files",
        lambda: ["docs/history/archive/governor-review-log/pr-100-old-backfill.md"],
    )
    seg = codex_gate.governor_changing_segment()
    assert seg is None


def test_sample_run_4_agents_md_wrong_pr_number_reminds(
    codex_gate, monkeypatch
) -> None:
    """(4) AGENTS.md + pr-99-*.md (different PR number) → reminder."""
    monkeypatch.setattr(
        codex_gate,
        "changed_files",
        lambda: [
            "AGENTS.md",
            "docs/history/archive/governor-review-log/pr-99-old.md",
        ],
    )
    monkeypatch.setattr(codex_gate, "pr_number_from_branch", lambda: 128)
    monkeypatch.setattr(codex_gate, "_read_latest_token", lambda _: None)
    seg = codex_gate.governor_changing_segment()
    assert seg is not None
    assert "128" in seg


# ---------------------------------------------------------------------------
# IC-11 lifecycle: consume_phase2_markers
# ---------------------------------------------------------------------------
def test_consume_phase2_markers_deletes_files(codex_gate, tmp_path) -> None:
    marker = _write_marker(tmp_path, "trivial")
    assert marker.exists()
    codex_gate.consume_phase2_markers(tmp_path)
    assert not marker.exists()


def test_consume_phase2_markers_idempotent(codex_gate, tmp_path) -> None:
    codex_gate.consume_phase2_markers(tmp_path)  # nonexistent dir — no crash
    codex_gate.consume_phase2_markers(tmp_path)


def test_consume_phase2_markers_then_read_is_none(codex_gate, tmp_path) -> None:
    _write_marker(tmp_path, "trivial")
    codex_gate.consume_phase2_markers(tmp_path)
    assert codex_gate._read_latest_token(tmp_path) is None


def test_24h_stale_marker_ignored_by_reader(codex_gate, tmp_path) -> None:
    old_ts = time.strftime(
        "%Y-%m-%dT%H:%M:%SZ",
        time.gmtime(time.time() - 90000),  # 25h ago
    )
    _write_marker(tmp_path, "trivial", ts=old_ts)
    assert codex_gate._read_latest_token(tmp_path) is None


# ---------------------------------------------------------------------------
# cleanup_stale_verify_logs
# ---------------------------------------------------------------------------
def test_cleanup_stale_verify_logs_removes_old_other_session(
    codex_gate, tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("CODEX_THREAD_ID", "current-session")
    monkeypatch.delenv("CODEX_SESSION_ID", raising=False)
    old_log = tmp_path / "verify-log-other-session.json"
    old_log.write_text("{}\n", encoding="utf-8")
    # Set mtime to 25h ago
    stale_mtime = time.time() - 90000
    import os

    os.utime(old_log, (stale_mtime, stale_mtime))
    codex_gate.cleanup_stale_verify_logs(tmp_path)
    assert not old_log.exists()


def test_cleanup_stale_verify_logs_preserves_current_session(
    codex_gate, tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("CODEX_THREAD_ID", "current-session")
    monkeypatch.delenv("CODEX_SESSION_ID", raising=False)
    # The current session log must never be deleted.
    # session_id is imported into codex_gate's namespace from verify_first.
    current_log = tmp_path / f"verify-log-{codex_gate.session_id()}.json"
    current_log.write_text("{}\n", encoding="utf-8")
    stale_mtime = time.time() - 90000
    import os

    os.utime(current_log, (stale_mtime, stale_mtime))
    codex_gate.cleanup_stale_verify_logs(tmp_path)
    assert current_log.exists()


# ---------------------------------------------------------------------------
# Fail-open smokes (HC-4.7)
# ---------------------------------------------------------------------------
def test_governor_changing_segment_silent_when_no_changed_files(
    codex_gate, monkeypatch
) -> None:
    monkeypatch.setattr(codex_gate, "changed_files", lambda: [])
    assert codex_gate.governor_changing_segment() is None


def test_governor_changing_segment_silent_on_exploration_token(
    codex_gate, monkeypatch
) -> None:
    monkeypatch.setattr(codex_gate, "changed_files", lambda: ["AGENTS.md"])
    monkeypatch.setattr(codex_gate, "_read_latest_token", lambda _: "exploration")
    assert codex_gate.governor_changing_segment() is None


def test_governor_changing_segment_silent_on_탐색_token(
    codex_gate, monkeypatch
) -> None:
    monkeypatch.setattr(codex_gate, "changed_files", lambda: ["AGENTS.md"])
    monkeypatch.setattr(codex_gate, "_read_latest_token", lambda _: "탐색")
    assert codex_gate.governor_changing_segment() is None


def test_governor_changing_segment_no_pr_no_entry_uses_no_pr_reminder(
    codex_gate, monkeypatch
) -> None:
    monkeypatch.setattr(codex_gate, "changed_files", lambda: ["AGENTS.md"])
    monkeypatch.setattr(codex_gate, "pr_number_from_branch", lambda: None)
    monkeypatch.setattr(codex_gate, "_read_latest_token", lambda _: None)
    seg = codex_gate.governor_changing_segment()
    assert seg == codex_gate.GOVERNOR_REMINDER_NO_PR


def test_governor_changing_segment_no_pr_with_staged_entry_silent(
    codex_gate, monkeypatch
) -> None:
    """PR not created yet but some log entry staged → silent (plan §3.3 step 10)."""
    monkeypatch.setattr(
        codex_gate,
        "changed_files",
        lambda: [
            "AGENTS.md",
            "docs/history/archive/governor-review-log/pr-99-placeholder.md",
        ],
    )
    monkeypatch.setattr(codex_gate, "pr_number_from_branch", lambda: None)
    monkeypatch.setattr(codex_gate, "_read_latest_token", lambda _: None)
    seg = codex_gate.governor_changing_segment()
    assert seg is None


# ---------------------------------------------------------------------------
# ADR 047 D4 — sync-cosmetic carve-out wired into shim hooks
# ---------------------------------------------------------------------------
def test_claude_shim_silences_on_sync_cosmetic_subset(claude_gate, monkeypatch) -> None:
    """Self-loop scenario from ADR 047 — feature PR + cosmetic /sync-guidelines edit.

    Without the shim wiring, the Claude Stop hook would emit a Pillar 7
    reminder for AGENTS.md / .claude/rules/** despite the cosmetic-only
    nature of the rules edit. The wired shim must consult
    `_shared_is_sync_cosmetic_only` and silence.
    """

    monkeypatch.setattr(
        claude_gate,
        "_changed_files",
        lambda: [
            "src/user/domain/services/user_service.py",
            ".claude/rules/project-status.md",
        ],
    )
    monkeypatch.setattr(claude_gate, "_read_latest_token", lambda _: None)
    monkeypatch.setattr(claude_gate, "pr_number_from_branch", lambda: 200)
    monkeypatch.setattr(
        claude_gate, "_shared_is_sync_cosmetic_only", lambda _subset: True
    )

    assert claude_gate.governor_changing_segment() is None


def test_claude_shim_triggers_when_sync_cosmetic_returns_false(
    claude_gate, monkeypatch
) -> None:
    monkeypatch.setattr(
        claude_gate,
        "_changed_files",
        lambda: ["AGENTS.md", ".claude/rules/project-status.md"],
    )
    monkeypatch.setattr(claude_gate, "_read_latest_token", lambda _: None)
    monkeypatch.setattr(claude_gate, "pr_number_from_branch", lambda: 201)
    monkeypatch.setattr(
        claude_gate, "_shared_is_sync_cosmetic_only", lambda _subset: False
    )

    seg = claude_gate.governor_changing_segment()
    assert seg is not None
    assert "Governor Footer" in seg


def test_codex_shim_silences_on_sync_cosmetic_subset(codex_gate, monkeypatch) -> None:
    monkeypatch.setattr(
        codex_gate,
        "changed_files",
        lambda: [
            "src/user/domain/services/user_service.py",
            ".claude/rules/project-status.md",
        ],
    )
    monkeypatch.setattr(codex_gate, "_read_latest_token", lambda _: None)
    monkeypatch.setattr(codex_gate, "pr_number_from_branch", lambda: 202)
    monkeypatch.setattr(
        codex_gate, "_shared_is_sync_cosmetic_only", lambda _subset: True
    )

    assert codex_gate.governor_changing_segment() is None


def test_codex_shim_triggers_when_sync_cosmetic_returns_false(
    codex_gate, monkeypatch
) -> None:
    monkeypatch.setattr(
        codex_gate,
        "changed_files",
        lambda: ["AGENTS.md", ".claude/rules/project-status.md"],
    )
    monkeypatch.setattr(codex_gate, "_read_latest_token", lambda _: None)
    monkeypatch.setattr(codex_gate, "pr_number_from_branch", lambda: 203)
    monkeypatch.setattr(
        codex_gate, "_shared_is_sync_cosmetic_only", lambda _subset: False
    )

    seg = codex_gate.governor_changing_segment()
    assert seg is not None
    assert "Governor Footer" in seg
