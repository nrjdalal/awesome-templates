"""Plan→execute boundary gate tests (ADR 054).

Covers the sibling gate that keys off ``workflow.stage == "planned"`` — a plan
exists but ``/execute-plan`` has not been invoked. Two decision surfaces share
one core predicate:

- ``should_block_plan_execute_edit`` — Claude ``PreToolUse`` hard block. NO
  session dedup: it must hold on every edit until ``/execute-plan`` advances the
  stage (ADR054-G1 D5).
- ``should_plan_execute_gate`` — Codex Stop-time advisory. Adds once-per-session
  dedup (ADR 054 D8).

The ADR050-G1 promotion bar requires false-positive tests covering exploration,
trivial edits, and single-skill work; those live in the ``FALSE POSITIVE
SUITE`` block below. The block fires only in the narrow ``planned`` window and
never on ordinary idle/complete/executing work.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import time
import types
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SHARED_DIR = REPO_ROOT / ".agents" / "shared"
if str(SHARED_DIR) not in sys.path:
    sys.path.insert(0, str(SHARED_DIR))

from governor import write_marker  # noqa: E402
from governor.stage_gate import (  # noqa: E402
    PLAN_EXECUTE_GATED_STAGES,
    PLAN_EXECUTE_REMINDER,
    mark_fired,
    should_block_plan_execute_edit,
    should_plan_execute_gate,
)

FRESH_TS = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
STALE_TS = "2020-01-01T00:00:00Z"

# Every ledger stage that is NOT `planned` — the block must stay silent on all
# of them (idle/complete/blocked are the ADR 050 advisory's domain; executing/
# reviewing are legitimate active implementation; unknown stays silent).
NON_PLANNED_STAGES = [
    "idle",
    "executing",
    "reviewing",
    "complete",
    "blocked",
    "future-stage",
]


def _ledger(tmp_path: Path, stage: object) -> Path:
    ledger = tmp_path / "current-work.json"
    ledger.write_text(json.dumps({"workflow": {"stage": stage}}), encoding="utf-8")
    return ledger


def _payload(repo_root: Path, rel_path: str, session_id: str = "sess-1") -> dict:
    return {
        "session_id": session_id,
        "tool_input": {"file_path": str(repo_root / rel_path)},
    }


@pytest.fixture()
def state_dir(tmp_path: Path) -> Path:
    d = tmp_path / "state"
    d.mkdir()
    return d


# --- should_block_plan_execute_edit: the one true positive -----------------


def test_block_fires_on_planned_impl_edit(tmp_path: Path, state_dir: Path) -> None:
    ledger = _ledger(tmp_path, "planned")
    payload = _payload(tmp_path, "src/user/service.py")
    assert should_block_plan_execute_edit(
        payload, state_dir, ledger, repo_root=tmp_path
    )


def test_planned_is_the_only_gated_stage() -> None:
    assert frozenset({"planned"}) == PLAN_EXECUTE_GATED_STAGES


# --- FALSE POSITIVE SUITE (ADR050-G1 promotion bar) ------------------------


@pytest.mark.parametrize("stage", NON_PLANNED_STAGES)
def test_block_silent_on_every_non_planned_stage(
    tmp_path: Path, state_dir: Path, stage: str
) -> None:
    """Single-skill / exploration / ordinary work runs at idle/complete/etc. —
    never blocked. Only the deliberate `planned` window gates."""
    ledger = _ledger(tmp_path, stage)
    payload = _payload(tmp_path, "src/user/service.py")
    assert not should_block_plan_execute_edit(
        payload, state_dir, ledger, repo_root=tmp_path
    )


@pytest.mark.parametrize("token", ["trivial", "자명", "hotfix", "긴급"])
def test_block_silent_when_plan_waiver_token_active(
    tmp_path: Path, state_dir: Path, token: str
) -> None:
    """Trivial / hotfix edits are explicitly licensed even while `planned`."""
    write_marker(
        {"matched": True, "token": token, "rationale_required": True}, state_dir
    )
    ledger = _ledger(tmp_path, "planned")
    payload = _payload(tmp_path, "src/user/service.py")
    assert not should_block_plan_execute_edit(
        payload, state_dir, ledger, repo_root=tmp_path
    )


@pytest.mark.parametrize("token", ["exploration", "탐색"])
def test_block_not_suppressed_by_exploration_token(
    tmp_path: Path, state_dir: Path, token: str
) -> None:
    """[exploration] declares a read-only session; it does not waive the plan→
    execute block (ADR 054 D6) — an impl edit while `planned` is still a signal.
    (In practice exploration sessions sit at `idle`, so the block rarely applies
    — but the token itself must not license bypassing an approved plan.)"""
    write_marker(
        {"matched": True, "token": token, "rationale_required": True}, state_dir
    )
    ledger = _ledger(tmp_path, "planned")
    payload = _payload(tmp_path, "src/user/service.py")
    assert should_block_plan_execute_edit(
        payload, state_dir, ledger, repo_root=tmp_path
    )


@pytest.mark.parametrize(
    "rel",
    [
        "tests/unit/user/test_user.py",
        "docs/ai/shared/project-dna.md",
        "src/user/README.md",
        "tools/check_examples_copyflow.py",
        ".claude/hooks/pre_tool_stage_block.py",
    ],
)
def test_block_silent_on_non_implementation_paths(
    tmp_path: Path, state_dir: Path, rel: str
) -> None:
    ledger = _ledger(tmp_path, "planned")
    payload = _payload(tmp_path, rel)
    assert not should_block_plan_execute_edit(
        payload, state_dir, ledger, repo_root=tmp_path
    )


def test_block_fail_open_on_missing_ledger(tmp_path: Path, state_dir: Path) -> None:
    payload = _payload(tmp_path, "src/user/service.py")
    assert not should_block_plan_execute_edit(
        payload, state_dir, tmp_path / "absent.json", repo_root=tmp_path
    )


def test_block_fail_open_on_malformed_payload(tmp_path: Path, state_dir: Path) -> None:
    ledger = _ledger(tmp_path, "planned")
    assert not should_block_plan_execute_edit({}, state_dir, ledger, repo_root=tmp_path)
    assert not should_block_plan_execute_edit(
        {"tool_input": "junk"}, state_dir, ledger, repo_root=tmp_path
    )
    assert not should_block_plan_execute_edit(
        {"tool_input": {"file_path": 42}}, state_dir, ledger, repo_root=tmp_path
    )


# --- the block does NOT dedup (ADR054-G1 D5) -------------------------------


def test_block_holds_on_every_edit_no_session_dedup(
    tmp_path: Path, state_dir: Path
) -> None:
    """Unlike the advisory, the block must not fire-once: marking the session as
    fired (the advisory dedup) must not release the block on the next edit."""
    ledger = _ledger(tmp_path, "planned")
    payload = _payload(tmp_path, "src/user/service.py", session_id="sess-A")
    assert should_block_plan_execute_edit(
        payload, state_dir, ledger, repo_root=tmp_path
    )
    mark_fired(state_dir, "sess-A")
    assert should_block_plan_execute_edit(
        payload, state_dir, ledger, repo_root=tmp_path
    )


# --- should_plan_execute_gate (Codex advisory) — DOES dedup ----------------


def test_advisory_fires_then_dedups(tmp_path: Path, state_dir: Path) -> None:
    ledger = _ledger(tmp_path, "planned")
    payload = _payload(tmp_path, "src/user/service.py", session_id="sess-A")
    assert should_plan_execute_gate(payload, state_dir, ledger, repo_root=tmp_path)
    mark_fired(state_dir, "sess-A")
    assert not should_plan_execute_gate(payload, state_dir, ledger, repo_root=tmp_path)


@pytest.mark.parametrize("stage", NON_PLANNED_STAGES)
def test_advisory_silent_on_non_planned(
    tmp_path: Path, state_dir: Path, stage: str
) -> None:
    ledger = _ledger(tmp_path, stage)
    payload = _payload(tmp_path, "src/user/service.py")
    assert not should_plan_execute_gate(payload, state_dir, ledger, repo_root=tmp_path)


# --- locale identity (ADR050-G4 pattern) -----------------------------------


def test_locale_en_reexports_canonical_reminder() -> None:
    from governor.locale import get_locale_string

    assert get_locale_string("PLAN_EXECUTE_REMINDER") == PLAN_EXECUTE_REMINDER


def test_locale_ko_translation_present(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_LOCALE", "ko")
    from governor.locale import get_locale_string

    rendered = get_locale_string("PLAN_EXECUTE_REMINDER")
    assert rendered
    assert rendered != PLAN_EXECUTE_REMINDER
    assert rendered.startswith("[stage-gate]")


# --- Claude PreToolUse block hook subprocess smokes ------------------------

BLOCK_HOOK = REPO_ROOT / ".claude" / "hooks" / "pre_tool_stage_block.py"


def _seed_state_root(tmp_path: Path, stage: str, token: str | None = None) -> Path:
    state_root = tmp_path / "state-root"
    ledger_dir = state_root / ".agents" / "state"
    ledger_dir.mkdir(parents=True)
    (ledger_dir / "current-work.json").write_text(
        json.dumps({"workflow": {"stage": stage}}), encoding="utf-8"
    )
    claude_state = state_root / ".claude" / "state"
    claude_state.mkdir(parents=True)
    if token is not None:
        (claude_state / "exception-token-x.json").write_text(
            json.dumps(
                {
                    "matched": True,
                    "token": token,
                    "rationale_required": True,
                    "ts": FRESH_TS,
                }
            ),
            encoding="utf-8",
        )
    return state_root


def _run_block(stdin_text: str, state_root: Path) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["HARNESS_STATE_ROOT"] = str(state_root)
    env.pop("AGENT_LOCALE", None)
    return subprocess.run(  # noqa: S603
        [sys.executable, str(BLOCK_HOOK)],
        input=stdin_text,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


def _edit_payload(rel: str = "src/user/x.py") -> str:
    return json.dumps(
        {
            "session_id": "smoke",
            "tool_name": "Edit",
            "tool_input": {"file_path": str(REPO_ROOT / rel)},
        }
    )


def test_block_hook_blocks_on_planned(tmp_path: Path) -> None:
    result = _run_block(_edit_payload(), _seed_state_root(tmp_path, "planned"))
    assert result.returncode == 2
    assert "[BLOCKED]" in result.stderr
    assert "planned" in result.stderr


def test_block_hook_holds_on_repeat(tmp_path: Path) -> None:
    """No session dedup at the hook level either — every invocation blocks."""
    state_root = _seed_state_root(tmp_path, "planned")
    assert _run_block(_edit_payload(), state_root).returncode == 2
    assert _run_block(_edit_payload(), state_root).returncode == 2


@pytest.mark.parametrize("stage", ["executing", "idle", "complete", "reviewing"])
def test_block_hook_allows_non_planned(tmp_path: Path, stage: str) -> None:
    result = _run_block(_edit_payload(), _seed_state_root(tmp_path, stage))
    assert result.returncode == 0
    assert result.stderr == ""


def test_block_hook_allows_non_impl_path(tmp_path: Path) -> None:
    result = _run_block(
        _edit_payload("docs/x.md"), _seed_state_root(tmp_path, "planned")
    )
    assert result.returncode == 0


@pytest.mark.parametrize("token", ["trivial", "hotfix"])
def test_block_hook_allows_with_waiver_token(tmp_path: Path, token: str) -> None:
    result = _run_block(
        _edit_payload(), _seed_state_root(tmp_path, "planned", token=token)
    )
    assert result.returncode == 0


@pytest.mark.parametrize("stdin_text", ["", "not json", '["list"]'])
def test_block_hook_fail_open_on_bad_stdin(tmp_path: Path, stdin_text: str) -> None:
    result = _run_block(stdin_text, _seed_state_root(tmp_path, "planned"))
    assert result.returncode == 0


# --- Codex Stop-hook plan_execute_segment ----------------------------------

_CODEX_HOOKS = REPO_ROOT / ".codex" / "hooks"
_CODEX_STOP_HOOK = _CODEX_HOOKS / "stop-sync-reminder.py"


def _load_codex_stop_hook() -> types.ModuleType:
    saved = {name: sys.modules.pop(name, None) for name in ("_shared", "_codex_stop")}
    try:
        for name, path in (
            ("_shared", _CODEX_HOOKS / "_shared.py"),
            ("_codex_stop", _CODEX_STOP_HOOK),
        ):
            spec = importlib.util.spec_from_file_location(name, path)
            assert spec is not None and spec.loader is not None
            mod = importlib.util.module_from_spec(spec)
            sys.modules[name] = mod
            spec.loader.exec_module(mod)
        return sys.modules["_codex_stop"]
    finally:
        for name, mod in saved.items():
            if mod is not None:
                sys.modules[name] = mod
            else:
                sys.modules.pop(name, None)


_STOP = _load_codex_stop_hook()
_plan_execute_segment = _STOP.plan_execute_segment


def _codex_seg(
    changed: list[str],
    tmp_path: Path,
    state_dir: Path,
    stage: str = "planned",
    sid: str = "sess-1",
) -> str | None:
    return _plan_execute_segment(
        changed,
        sid,
        state_dir=state_dir,
        ledger_path=_ledger(tmp_path, stage),
        repo_root=tmp_path,
    )


def test_codex_segment_fires_on_planned(tmp_path: Path, state_dir: Path) -> None:
    assert (
        _codex_seg(["src/user/service.py"], tmp_path, state_dir)
        == PLAN_EXECUTE_REMINDER
    )


@pytest.mark.parametrize("stage", NON_PLANNED_STAGES)
def test_codex_segment_silent_on_non_planned(
    tmp_path: Path, state_dir: Path, stage: str
) -> None:
    assert _codex_seg(["src/user/service.py"], tmp_path, state_dir, stage=stage) is None


def test_codex_segment_silent_on_missing_ledger(
    tmp_path: Path, state_dir: Path
) -> None:
    seg = _plan_execute_segment(
        ["src/user/service.py"],
        "sess-1",
        state_dir=state_dir,
        ledger_path=tmp_path / "absent.json",
        repo_root=tmp_path,
    )
    assert seg is None


def test_codex_segment_fires_on_mixed_set(tmp_path: Path, state_dir: Path) -> None:
    seg = _codex_seg(
        ["tests/unit/x_test.py", "docs/note.md", "src/user/service.py"],
        tmp_path,
        state_dir,
    )
    assert seg == PLAN_EXECUTE_REMINDER


@pytest.mark.parametrize(
    "changed",
    [[], ["tests/unit/user/test_user.py"], [".codex/hooks/stop-sync-reminder.py"]],
)
def test_codex_segment_silent_without_impl_source(
    tmp_path: Path, state_dir: Path, changed: list[str]
) -> None:
    assert _codex_seg(changed, tmp_path, state_dir) is None


@pytest.mark.parametrize("token", ["trivial", "자명", "hotfix", "긴급"])
def test_codex_segment_silent_on_plan_waiver_token(
    tmp_path: Path, state_dir: Path, token: str
) -> None:
    write_marker(
        {"matched": True, "token": token, "rationale_required": True}, state_dir
    )
    assert _codex_seg(["src/user/service.py"], tmp_path, state_dir) is None


@pytest.mark.parametrize("token", ["exploration", "탐색"])
def test_codex_segment_exploration_does_not_suppress(
    tmp_path: Path, state_dir: Path, token: str
) -> None:
    write_marker(
        {"matched": True, "token": token, "rationale_required": True}, state_dir
    )
    assert (
        _codex_seg(["src/user/service.py"], tmp_path, state_dir)
        == PLAN_EXECUTE_REMINDER
    )


def test_codex_segment_dedup_after_mark_fired(tmp_path: Path, state_dir: Path) -> None:
    changed = ["src/user/service.py"]
    assert (
        _codex_seg(changed, tmp_path, state_dir, sid="sess-A") == PLAN_EXECUTE_REMINDER
    )
    mark_fired(state_dir, "sess-A")
    assert _codex_seg(changed, tmp_path, state_dir, sid="sess-A") is None


def test_codex_segment_ko_locale_renders(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, state_dir: Path
) -> None:
    monkeypatch.setenv("AGENT_LOCALE", "ko")
    seg = _codex_seg(["src/user/service.py"], tmp_path, state_dir)
    assert seg and seg != PLAN_EXECUTE_REMINDER and seg.startswith("[stage-gate]")


# --- static guards: reminder imported, never inlined -----------------------


def test_claude_block_hook_imports_reminder_never_inline() -> None:
    text = BLOCK_HOOK.read_text(encoding="utf-8")
    assert "should_block_plan_execute_edit" in text
    assert "PLAN_EXECUTE_REMINDER" in text
    # Canonical reminder body must never be duplicated inside the hook.
    assert "An approved plan exists but execution has not formally started" not in text


def test_codex_hook_imports_plan_execute_reminder_never_inline() -> None:
    text = _CODEX_STOP_HOOK.read_text(encoding="utf-8")
    assert "plan_execute_segment" in text
    assert "PLAN_EXECUTE_REMINDER" in text
    assert "An approved plan exists but execution has not formally started" not in text
