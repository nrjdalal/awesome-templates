"""Mid-task stage-gate policy tests (ADR 050, issue #268).

Covers the pure decision surface of ``governor.stage_gate``:

- fires on: gated stage (idle/complete/blocked) + ``.py`` under
  ``src/``/``examples/`` + no token marker + first time this session
- silent on: active stages, unknown stage strings, missing/corrupt
  ledger, exception-token markers, non-implementation paths,
  already-fired sessions (fail-open everywhere, ADR050-G2)
- marker lifecycle: once-per-session dedup, 24h window, self-pruning
- locale: ``STAGE_GATE_REMINDER`` re-export identity (ADR050-G4)
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SHARED_DIR = REPO_ROOT / ".agents" / "shared"
if str(SHARED_DIR) not in sys.path:
    sys.path.insert(0, str(SHARED_DIR))

from governor import write_marker  # noqa: E402
from governor.stage_gate import (  # noqa: E402
    GATED_STAGES,
    STAGE_GATE_REMINDER,
    extract_session_id,
    has_fired_this_session,
    is_implementation_source,
    mark_fired,
    read_ledger_stage,
    should_stage_gate,
)

FRESH_TS = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
STALE_TS = "2020-01-01T00:00:00Z"


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


# --- read_ledger_stage -------------------------------------------------


def test_read_stage_happy_path(tmp_path: Path) -> None:
    assert read_ledger_stage(_ledger(tmp_path, "complete")) == "complete"


@pytest.mark.parametrize(
    "content",
    [
        "not json {",
        json.dumps([1, 2]),
        json.dumps({"workflow": "oops"}),
        json.dumps({"workflow": {"stage": 7}}),
    ],
)
def test_read_stage_fail_open_on_bad_shape(tmp_path: Path, content: str) -> None:
    ledger = tmp_path / "current-work.json"
    ledger.write_text(content, encoding="utf-8")
    assert read_ledger_stage(ledger) is None


def test_read_stage_missing_file(tmp_path: Path) -> None:
    assert read_ledger_stage(tmp_path / "nope.json") is None


# --- is_implementation_source ------------------------------------------


@pytest.mark.parametrize(
    "rel", ["src/user/domain/services/user_service.py", "examples/todo/bootstrap.py"]
)
def test_implementation_paths_absolute(tmp_path: Path, rel: str) -> None:
    assert is_implementation_source(str(tmp_path / rel), repo_root=tmp_path)


def test_implementation_path_relative(tmp_path: Path) -> None:
    assert is_implementation_source("src/foo/bar.py", repo_root=tmp_path)


@pytest.mark.parametrize(
    "rel",
    [
        "tests/unit/user/test_user.py",
        "docs/ai/shared/project-dna.md",
        "src/user/README.md",
        "tools/check_examples_copyflow.py",
        ".claude/hooks/verify_first.py",
    ],
)
def test_non_implementation_paths_silent(tmp_path: Path, rel: str) -> None:
    assert not is_implementation_source(str(tmp_path / rel), repo_root=tmp_path)


def test_path_outside_repo_root_silent(tmp_path: Path) -> None:
    outside = tmp_path / "elsewhere" / "src" / "x.py"
    repo = tmp_path / "repo"
    repo.mkdir()
    assert not is_implementation_source(str(outside), repo_root=repo)


def test_none_and_empty_path_silent(tmp_path: Path) -> None:
    assert not is_implementation_source(None, repo_root=tmp_path)
    assert not is_implementation_source("", repo_root=tmp_path)


def test_relative_traversal_normalised(tmp_path: Path) -> None:
    """R1.2: `..` segments are resolved before the prefix check."""
    assert not is_implementation_source("src/../tests/foo.py", repo_root=tmp_path)
    assert is_implementation_source("examples/../src/x.py", repo_root=tmp_path)
    assert not is_implementation_source(
        str(tmp_path / "src" / ".." / "tools" / "x.py"), repo_root=tmp_path
    )


# --- should_stage_gate decision matrix ----------------------------------


@pytest.mark.parametrize("stage", sorted(GATED_STAGES))
def test_fires_on_gated_stages(tmp_path: Path, state_dir: Path, stage: str) -> None:
    ledger = _ledger(tmp_path, stage)
    payload = _payload(tmp_path, "src/user/service.py")
    assert should_stage_gate(payload, state_dir, ledger, repo_root=tmp_path)


@pytest.mark.parametrize("stage", ["planned", "executing", "reviewing", "future-stage"])
def test_silent_on_active_or_unknown_stages(
    tmp_path: Path, state_dir: Path, stage: str
) -> None:
    ledger = _ledger(tmp_path, stage)
    payload = _payload(tmp_path, "src/user/service.py")
    assert not should_stage_gate(payload, state_dir, ledger, repo_root=tmp_path)


def test_silent_on_missing_ledger(tmp_path: Path, state_dir: Path) -> None:
    payload = _payload(tmp_path, "src/user/service.py")
    assert not should_stage_gate(
        payload, state_dir, tmp_path / "absent.json", repo_root=tmp_path
    )


@pytest.mark.parametrize("token", ["trivial", "자명", "hotfix", "긴급"])
def test_silent_when_plan_waiver_token_active(
    tmp_path: Path, state_dir: Path, token: str
) -> None:
    write_marker(
        {"matched": True, "token": token, "rationale_required": True}, state_dir
    )
    ledger = _ledger(tmp_path, "complete")
    payload = _payload(tmp_path, "src/user/service.py")
    assert not should_stage_gate(payload, state_dir, ledger, repo_root=tmp_path)


@pytest.mark.parametrize("token", ["exploration", "탐색"])
def test_exploration_token_does_not_suppress(
    tmp_path: Path, state_dir: Path, token: str
) -> None:
    """R1.1: [exploration] declares a read-only session — an implementation
    edit under it is itself a signal, so the gate still fires."""
    write_marker(
        {"matched": True, "token": token, "rationale_required": True}, state_dir
    )
    ledger = _ledger(tmp_path, "complete")
    payload = _payload(tmp_path, "src/user/service.py")
    assert should_stage_gate(payload, state_dir, ledger, repo_root=tmp_path)


def test_silent_on_malformed_payload(tmp_path: Path, state_dir: Path) -> None:
    ledger = _ledger(tmp_path, "complete")
    assert not should_stage_gate({}, state_dir, ledger, repo_root=tmp_path)
    assert not should_stage_gate(
        {"tool_input": "junk"}, state_dir, ledger, repo_root=tmp_path
    )
    assert not should_stage_gate(
        {"tool_input": {"file_path": 42}}, state_dir, ledger, repo_root=tmp_path
    )


# --- once-per-session dedup ---------------------------------------------


def test_dedup_within_session(tmp_path: Path, state_dir: Path) -> None:
    ledger = _ledger(tmp_path, "idle")
    payload = _payload(tmp_path, "src/user/service.py", session_id="sess-A")
    assert should_stage_gate(payload, state_dir, ledger, repo_root=tmp_path)
    mark_fired(state_dir, "sess-A")
    assert not should_stage_gate(payload, state_dir, ledger, repo_root=tmp_path)


def test_other_session_still_fires(tmp_path: Path, state_dir: Path) -> None:
    ledger = _ledger(tmp_path, "idle")
    mark_fired(state_dir, "sess-A")
    payload = _payload(tmp_path, "src/user/service.py", session_id="sess-B")
    assert should_stage_gate(payload, state_dir, ledger, repo_root=tmp_path)


def test_stale_session_marker_does_not_dedup(state_dir: Path) -> None:
    marker = state_dir / "stage-gate-sess-A.json"
    marker.write_text(
        json.dumps({"session_id": "sess-A", "ts": STALE_TS}), encoding="utf-8"
    )
    assert not has_fired_this_session(state_dir, "sess-A")


def test_mark_fired_prunes_stale_and_corrupt_markers(state_dir: Path) -> None:
    stale = state_dir / "stage-gate-old.json"
    stale.write_text(json.dumps({"ts": STALE_TS}), encoding="utf-8")
    corrupt = state_dir / "stage-gate-bad.json"
    corrupt.write_text("not json", encoding="utf-8")
    fresh = mark_fired(state_dir, "sess-new")
    assert fresh is not None and fresh.exists()
    assert not stale.exists()
    assert not corrupt.exists()


def test_mark_fired_exclusive_claim(state_dir: Path) -> None:
    """R1.3: the second claim for the same fresh session returns None,
    so only the first writer emits."""
    first = mark_fired(state_dir, "sess-race")
    assert first is not None
    assert mark_fired(state_dir, "sess-race") is None


def test_mark_fired_reclaims_after_stale_marker(state_dir: Path) -> None:
    stale = state_dir / "stage-gate-sess-race.json"
    stale.write_text(json.dumps({"ts": STALE_TS}), encoding="utf-8")
    assert mark_fired(state_dir, "sess-race") is not None


def test_mark_fired_keeps_fresh_sibling_markers(state_dir: Path) -> None:
    sibling = state_dir / "stage-gate-sess-other.json"
    sibling.write_text(json.dumps({"ts": FRESH_TS}), encoding="utf-8")
    mark_fired(state_dir, "sess-new")
    assert sibling.exists()


def test_mark_fired_ignores_exception_token_namespace(state_dir: Path) -> None:
    token_marker = write_marker(
        {"matched": True, "token": "trivial", "rationale_required": True}, state_dir
    )
    assert token_marker is not None
    mark_fired(state_dir, "sess-new")
    assert token_marker.exists()


def test_extract_session_id_fallback() -> None:
    assert extract_session_id({}) == "unknown"
    assert extract_session_id({"session_id": ""}) == "unknown"
    assert extract_session_id({"session_id": "abc"}) == "abc"


def test_session_id_sanitised_in_marker_name(state_dir: Path) -> None:
    marker = mark_fired(state_dir, "weird/../id with spaces")
    assert marker is not None
    assert "/" not in marker.name.removeprefix("stage-gate-")
    assert " " not in marker.name


# --- locale re-export identity (ADR050-G4) ------------------------------


def test_locale_en_reexports_canonical_reminder() -> None:
    from governor.locale import get_locale_string

    assert get_locale_string("STAGE_GATE_REMINDER") == STAGE_GATE_REMINDER


def test_locale_ko_translation_present(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_LOCALE", "ko")
    from governor.locale import get_locale_string

    rendered = get_locale_string("STAGE_GATE_REMINDER")
    assert rendered
    assert rendered != STAGE_GATE_REMINDER
    assert rendered.startswith("[stage-gate]")


# --- Claude shim smokes (R2.1) -------------------------------------------

SHIM = REPO_ROOT / ".claude" / "hooks" / "post_tool_stage_gate.py"


def _run_shim(stdin_text: str, state_root: Path) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["HARNESS_STATE_ROOT"] = str(state_root)
    env.pop("AGENT_LOCALE", None)
    return subprocess.run(  # noqa: S603
        [sys.executable, str(SHIM)],
        input=stdin_text,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


def _seed_state_root(tmp_path: Path, stage: str) -> Path:
    state_root = tmp_path / "state-root"
    ledger_dir = state_root / ".agents" / "state"
    ledger_dir.mkdir(parents=True)
    (ledger_dir / "current-work.json").write_text(
        json.dumps({"workflow": {"stage": stage}}), encoding="utf-8"
    )
    return state_root


def _smoke_payload(session_id: str) -> str:
    return json.dumps(
        {
            "session_id": session_id,
            "tool_input": {"file_path": str(REPO_ROOT / "src" / "user" / "x.py")},
        }
    )


def test_shim_emits_additional_context_json(tmp_path: Path) -> None:
    result = _run_shim(
        _smoke_payload("smoke-1"), _seed_state_root(tmp_path, "complete")
    )
    assert result.returncode == 0
    out = json.loads(result.stdout)
    hook_out = out["hookSpecificOutput"]
    assert hook_out["hookEventName"] == "PostToolUse"
    assert hook_out["additionalContext"] == STAGE_GATE_REMINDER


def test_shim_second_run_is_silent(tmp_path: Path) -> None:
    state_root = _seed_state_root(tmp_path, "complete")
    assert _run_shim(_smoke_payload("smoke-2"), state_root).stdout != ""
    second = _run_shim(_smoke_payload("smoke-2"), state_root)
    assert second.returncode == 0
    assert second.stdout == ""


def test_shim_silent_on_active_stage(tmp_path: Path) -> None:
    result = _run_shim(
        _smoke_payload("smoke-3"), _seed_state_root(tmp_path, "executing")
    )
    assert result.returncode == 0
    assert result.stdout == ""


@pytest.mark.parametrize("stdin_text", ["", "not json", '["list"]'])
def test_shim_fail_open_on_bad_stdin(tmp_path: Path, stdin_text: str) -> None:
    result = _run_shim(stdin_text, _seed_state_root(tmp_path, "complete"))
    assert result.returncode == 0
    assert result.stdout == ""
