"""Native workflow contract tests for issue #257.

These tests pin the project-native replacement for the temporary
superpowers-inspired design lens:

* ``plan-feature`` produces an Execution Packet.
* ``execute-plan`` exists in the Hybrid C skill structure.
* The shared work ledger exposes v2 workflow state and advisory helpers.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SHARED_SKILLS = REPO_ROOT / "docs" / "ai" / "shared" / "skills"
CLAUDE_SKILLS = REPO_ROOT / ".claude" / "skills"
CODEX_SKILLS = REPO_ROOT / ".agents" / "skills"
CLAUDE_SESSION_START = REPO_ROOT / ".claude" / "hooks" / "session-start-context.sh"
CODEX_STOP_HOOK = REPO_ROOT / ".codex" / "hooks" / "stop-sync-reminder.py"

_SHARED = REPO_ROOT / ".agents" / "shared"
if str(_SHARED) not in sys.path:
    sys.path.insert(0, str(_SHARED))

import work_ledger as wl  # noqa: E402


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_execute_plan_hybrid_c_skill_exists_and_points_to_shared_procedure() -> None:
    """execute-plan must follow the existing Hybrid C skill split."""

    shared = SHARED_SKILLS / "execute-plan.md"
    claude = CLAUDE_SKILLS / "execute-plan" / "SKILL.md"
    codex = CODEX_SKILLS / "execute-plan" / "SKILL.md"

    assert shared.exists()
    assert claude.exists()
    assert codex.exists()

    shared_text = _text(shared)
    assert "## Default Flow Position" in shared_text
    assert "Execution Packet" in shared_text
    assert "update_workflow_state" in shared_text
    assert "cross-tool review" in shared_text
    assert "self-structured" in shared_text

    for wrapper in (claude, codex):
        wrapper_text = _text(wrapper)
        assert "docs/ai/shared/skills/execute-plan.md" in wrapper_text
        assert "execute-plan" in wrapper_text
        assert "Execution Packet" in wrapper_text


def test_plan_feature_documents_execution_packet_contract() -> None:
    """plan-feature output must include the fields execute-plan consumes."""

    required_terms = [
        "Execution Packet",
        "Goal",
        "Scope",
        "Success Criteria",
        "Selected Approach",
        "Architecture Impact",
        "Task List",
        "Verification Gates",
        "Review Gates",
        "update_workflow_state",
    ]

    paths = [
        SHARED_SKILLS / "plan-feature.md",
        CLAUDE_SKILLS / "plan-feature" / "SKILL.md",
        CODEX_SKILLS / "plan-feature" / "SKILL.md",
        REPO_ROOT / "docs" / "ai" / "shared" / "planning-checklists.md",
    ]

    for path in paths:
        text = _text(path)
        missing = [term for term in required_terms if term not in text]
        assert not missing, f"{path} missing Execution Packet terms: {missing}"


def test_target_operating_model_mentions_native_execute_plan_boundary() -> None:
    text = _text(REPO_ROOT / "docs" / "ai" / "shared" / "target-operating-model.md")
    assert "execute-plan" in text
    assert "superpowers" in text
    assert "native harness" in text
    assert "advisory-first" in text


def test_work_ledger_v2_default_workflow_shape() -> None:
    ledger = wl._default_ledger()

    assert ledger["schema_version"] == 2
    workflow = ledger["workflow"]
    assert workflow == {
        "stage": "idle",
        "plan_ref": None,
        "current_task": None,
        "tasks": [],
        "review": {
            "mode": None,
            "status": "not_required",
            "reason": None,
        },
    }


def test_workflow_state_update_preserves_task_and_review_data(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr(wl, "STATE_DIR", tmp_path)
    monkeypatch.setattr(wl, "LEDGER_PATH", tmp_path / "current-work.json")

    wl.update_workflow_state(
        stage="executing",
        plan_ref="docs/superpowers/plans/native-harness.md",
        current_task="Task 2: Ledger advisory",
        tasks=[
            {
                "id": "1",
                "title": "Execution Packet",
                "status": "completed",
            },
            {
                "id": "2",
                "title": "Ledger advisory",
                "status": "in_progress",
            },
        ],
        review_mode="self-structured",
        review_status="fallback",
        review_reason="Claude CLI authentication unavailable",
        updated_by="test",
    )

    ledger = wl.read_ledger()
    assert ledger is not None
    assert ledger["workflow"]["stage"] == "executing"
    assert ledger["workflow"]["plan_ref"] == "docs/superpowers/plans/native-harness.md"
    assert ledger["workflow"]["current_task"] == "Task 2: Ledger advisory"
    assert ledger["workflow"]["tasks"][1]["status"] == "in_progress"
    assert ledger["workflow"]["review"] == {
        "mode": "self-structured",
        "status": "fallback",
        "reason": "Claude CLI authentication unavailable",
    }


def test_workflow_advisory_segments_warn_for_missing_plan_and_review(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr(wl, "STATE_DIR", tmp_path)
    monkeypatch.setattr(wl, "LEDGER_PATH", tmp_path / "current-work.json")

    segments = wl.build_workflow_advisory_segments(
        changed_files=["AGENTS.md"],
        governor_changing=True,
    )

    joined = "\n".join(segments)
    assert "Native workflow advisory" in joined
    assert "Execution Packet" in joined
    assert "review state" in joined


def test_workflow_advisory_segments_warn_for_pending_verification(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr(wl, "STATE_DIR", tmp_path)
    monkeypatch.setattr(wl, "LEDGER_PATH", tmp_path / "current-work.json")

    ledger = wl._default_ledger()
    ledger["verification"]["status"] = "pending"
    ledger["verification"]["changed_py_files"] = ["src/user/domain/services/user.py"]
    wl.write_ledger(ledger, updated_by="test")

    segments = wl.build_workflow_advisory_segments(
        changed_files=["src/user/domain/services/user.py"],
        governor_changing=False,
    )

    joined = "\n".join(segments)
    assert "verification is pending" in joined
    assert "src/user/domain/services/user.py" in joined


def test_workflow_advisory_segments_fail_open_on_corrupt_ledger(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr(wl, "STATE_DIR", tmp_path)
    monkeypatch.setattr(wl, "LEDGER_PATH", tmp_path / "current-work.json")
    (tmp_path / "current-work.json").write_text("{not json", encoding="utf-8")

    segments = wl.build_workflow_advisory_segments(
        changed_files=["AGENTS.md"],
        governor_changing=True,
    )

    assert isinstance(segments, list)


def test_claude_session_start_expands_native_workflow_summary(tmp_path) -> None:
    state_dir = tmp_path / ".agents" / "state"
    state_dir.mkdir(parents=True)
    ledger = wl._default_ledger()
    ledger["workflow"]["stage"] = "executing"
    ledger["workflow"]["plan_ref"] = "issue #257"
    ledger["workflow"]["current_task"] = "Task 1"
    ledger["workflow"]["review"]["status"] = "pending"
    (state_dir / "current-work.json").write_text(json.dumps(ledger), encoding="utf-8")

    result = subprocess.run(  # noqa: S603
        ["bash", str(CLAUDE_SESSION_START)],
        cwd=REPO_ROOT,
        env={**__import__("os").environ, "HARNESS_STATE_ROOT": str(tmp_path)},
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "$SUMMARY" not in result.stdout
    assert "Stage    : executing" in result.stdout
    assert "Plan ref : issue #257" in result.stdout
    assert "Task     : Task 1" in result.stdout
    assert "Review   : pending" in result.stdout


def test_codex_stop_hook_refreshes_work_ledger_before_building_segments() -> None:
    source = CODEX_STOP_HOOK.read_text(encoding="utf-8")

    update_pos = source.index("update_verification_from_git()")
    # #269 passes the pre-computed changed set: `build_segments(changed)`.
    build_pos = source.index("segments = build_segments(")

    assert update_pos < build_pos, (
        "Codex Stop hook must refresh work-ledger verification state before "
        "building native workflow advisory segments."
    )
