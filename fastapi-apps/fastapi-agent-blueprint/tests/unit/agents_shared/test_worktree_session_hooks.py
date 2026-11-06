"""Hooks must act on the session's working tree, not on their own checkout (#425).

Claude Code desktop starts a worktree session with the worktree as its working
directory and the main checkout as ``--project-config-root``. Every command in
``.claude/settings.json`` is relative (``bash .claude/hooks/...``) and Claude
Code runs it from the config root, so a worktree session executes **main's**
hook copies. Those copies took every root from their own file location: the
session read and wrote main's work ledger and ``.claude/state``, classified its
edits against main's tree, and ran its Stop-time git in main. The payload's
``cwd`` is the only hook input that names the worktree — the process cwd and
``CLAUDE_PROJECT_DIR`` both point at the config root (measured on Claude Code
2.1.309 with capture hooks).

These tests rebuild that layout under ``tmp_path``: a "main" repository holding
a *copy* of the harness, with a linked worktree in ``.claude/worktrees/wt``.
Hooks run from the main copy, with the main checkout as process cwd and the
worktree as payload ``cwd``. Copying rather than symlinking is what makes a
pre-fix run safe: every root the old code derived from ``__file__`` lands inside
``tmp_path``, never in the operator's checkout. ``HARNESS_STATE_ROOT`` is removed
from the child environment on purpose — it is the override that would otherwise
hide which root a hook picked (#407 keeps it set for every other test).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_LIVE_LEDGER = _REPO_ROOT / ".agents" / "state" / "current-work.json"

# What the hooks need at runtime, copied into the temporary main checkout.
_COPIED_DIRS = (
    ".agents/shared",
    ".claude/hooks",
    ".codex/hooks",
    ".antigravity/hooks",
)
_COPIED_FILES = (".gitignore", "docs/ai/shared/governor-paths.md")

_LAUNCHER = ".agents/shared/harness-python.sh"

# Entry points exactly as registered in .claude/settings.json, .codex/hooks.json
# and .gemini/settings.json, each run from the main checkout the way Claude Code
# desktop runs a worktree session's hooks. Codex and Gemini run hooks from the
# session's own checkout instead; holding them to the same layout pins the shared
# ledger contract, not their runtime.
_USER_PROMPT_SUBMIT = {
    "claude": ["bash", ".claude/hooks/user-prompt-submit.sh"],
    "codex": ["sh", _LAUNCHER, ".codex/hooks/user-prompt-submit.py"],
    "antigravity": ["sh", _LAUNCHER, ".antigravity/hooks/user-prompt-submit.py"],
}
_SESSION_START = {
    "claude": ["bash", ".claude/hooks/session-start-context.sh"],
    "codex": ["sh", _LAUNCHER, ".codex/hooks/session-start.py"],
    "antigravity": ["sh", _LAUNCHER, ".antigravity/hooks/session-start.py"],
}
_STOP = {
    "claude": ["bash", ".claude/hooks/stop-sync-reminder.sh"],
    "codex": ["sh", _LAUNCHER, ".codex/hooks/stop-sync-reminder.py"],
    "antigravity": ["sh", _LAUNCHER, ".antigravity/hooks/stop-sync-reminder.py"],
}
_CLAUDE_STAGE_BLOCK = ["bash", ".claude/hooks/pre-tool-stage-block.sh"]
_CLAUDE_STAGE_GATE = ["bash", ".claude/hooks/stage-gate.sh"]
_CLAUDE_STOP = _STOP["claude"]

# A sync-cosmetic file (ADR 047 D4): committed, so a worktree edit to it shows up
# in `git diff` — the carve-out treats an *empty* diff as cosmetic.
_COSMETIC_RULES = ".claude/rules/project-overview.md"


@dataclass(frozen=True)
class DesktopLayout:
    """A main checkout with the harness, and a worktree nested under it."""

    main: Path
    worktree: Path

    def ledger(self, root: Path) -> Path:
        return root / ".agents" / "state" / "current-work.json"


def _git(cwd: Path, *args: str) -> None:
    # The operator's global git config (signing, hooksPath, default branch) has
    # no business in a fixture repository.
    env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
    subprocess.run(  # noqa: S603
        ["git", *args],  # noqa: S607
        cwd=cwd,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )


@pytest.fixture
def layout(tmp_path: Path) -> DesktopLayout:
    main = tmp_path / "main"
    for rel in _COPIED_DIRS:
        shutil.copytree(
            _REPO_ROOT / rel,
            main / rel,
            ignore=shutil.ignore_patterns("__pycache__", "state"),
        )
    for rel in _COPIED_FILES:
        (main / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(_REPO_ROOT / rel, main / rel)
    # harness-python.sh recognises a project root by pyproject.toml + .agents/.
    (main / "pyproject.toml").write_text(
        '[project]\nname = "layout"\nversion = "0"\n', encoding="utf-8"
    )
    (main / _COSMETIC_RULES).parent.mkdir(parents=True)
    (main / _COSMETIC_RULES).write_text(
        "# Commands\n\n> Last synced: 2026-01-01\n", encoding="utf-8"
    )
    _git(main, "init", "-q", "-b", "main")
    _git(main, "add", "-A")
    _git(
        main,
        "-c",
        "user.name=layout",
        "-c",
        "user.email=layout@example.invalid",
        "commit",
        "-q",
        "-m",
        "layout",
    )
    worktree = main / ".claude" / "worktrees" / "wt"
    _git(main, "worktree", "add", "-q", "-b", "wt", str(worktree))
    return DesktopLayout(main=main.resolve(), worktree=worktree.resolve())


@pytest.fixture(autouse=True)
def _live_ledger_untouched() -> Iterator[None]:
    """Belt and braces: nothing here may write the checkout under test."""

    def fingerprint() -> str | None:
        try:
            return _LIVE_LEDGER.read_text(encoding="utf-8")
        except OSError:
            return None

    before = fingerprint()
    yield
    assert fingerprint() == before, f"{_LIVE_LEDGER} was modified by a #425 test"


def _run(
    layout: DesktopLayout,
    argv: list[str],
    payload: dict[str, object],
    *,
    state_root: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run a hook from the main copy; ``state_root`` sets HARNESS_STATE_ROOT."""
    env = {
        key: value
        for key, value in os.environ.items()
        if key not in ("HARNESS_STATE_ROOT", "AGENT_LOCALE", "CLAUDE_SESSION_ID")
    }
    if state_root is not None:
        env["HARNESS_STATE_ROOT"] = str(state_root)
    # The launcher would otherwise look for main/.venv and then try `uv run`.
    env["HARNESS_PYTHON_VENV"] = sys.executable
    # Stable identity for the active stage and token lifecycle.
    env["CLAUDE_CODE_HOST_SESSION_ID"] = "wt-session"
    return subprocess.run(  # noqa: S603
        argv,
        cwd=layout.main,
        input=json.dumps(payload),
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )


def _write_ledger(path: Path, **fields: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"schema_version": 2, **fields}, ensure_ascii=False),
        encoding="utf-8",
    )


def _edit_payload(layout: DesktopLayout, rel: str) -> dict[str, object]:
    return {
        "session_id": "wt-session",
        "cwd": str(layout.worktree),
        "hook_event_name": "PreToolUse",
        "tool_name": "Edit",
        "tool_input": {"file_path": str(layout.worktree / rel)},
    }


# ---------------------------------------------------------------------------
# Stage gates: a worktree edit is an implementation edit of *that* tree
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("main_stage", [None, "planned"])
def test_stage_block_blocks_a_worktree_edit_while_its_plan_is_unexecuted(
    layout: DesktopLayout, main_stage: str | None
) -> None:
    """ADR 054's hard block must hold for an edit in the session's worktree.

    Before #425 main's copy measured the edit against main's tree, saw
    ``.claude/worktrees/wt/src/...`` — first component ``.claude`` — and let it
    through. ``main_stage="planned"`` isolates that half: even with main's
    ledger also planned, only the classification can make it pass.
    """
    _write_ledger(layout.ledger(layout.worktree), workflow={"stage": "planned"})
    if main_stage is not None:
        _write_ledger(layout.ledger(layout.main), workflow={"stage": main_stage})

    result = _run(
        layout, _CLAUDE_STAGE_BLOCK, _edit_payload(layout, "src/app/service.py")
    )

    assert result.returncode == 2, (result.returncode, result.stderr)
    assert "[BLOCKED] plan→execute boundary" in result.stderr


def test_stage_block_reads_the_worktrees_ledger_not_mains(
    layout: DesktopLayout,
) -> None:
    """The stage comes from the session's ledger, so main's plan cannot block it.

    Guards the half-fix that classifies against the worktree but still reads
    main's ledger.
    """
    _write_ledger(layout.ledger(layout.worktree), workflow={"stage": "executing"})
    _write_ledger(layout.ledger(layout.main), workflow={"stage": "planned"})

    result = _run(
        layout, _CLAUDE_STAGE_BLOCK, _edit_payload(layout, "src/app/service.py")
    )

    assert result.returncode == 0, result.stderr


def test_stage_gate_advises_on_a_worktree_edit_with_no_plan(
    layout: DesktopLayout,
) -> None:
    """ADR 050's advisory fires for the worktree, and dedups in its state dir."""
    _write_ledger(layout.ledger(layout.worktree), workflow={"stage": "idle"})
    _write_ledger(layout.ledger(layout.main), workflow={"stage": "executing"})

    result = _run(
        layout, _CLAUDE_STAGE_GATE, _edit_payload(layout, "src/app/service.py")
    )

    assert result.returncode == 0, result.stderr
    advisory = json.loads(result.stdout)
    assert "[stage-gate]" in advisory["hookSpecificOutput"]["additionalContext"]
    markers = list((layout.worktree / ".claude" / "state").glob("stage-gate-*.json"))
    assert len(markers) == 1
    assert not (layout.main / ".claude" / "state").exists()


# ---------------------------------------------------------------------------
# .claude/state: the session's markers and logs, read and written in one place
# ---------------------------------------------------------------------------


def _write_token_marker(state_dir: Path, token: str) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "exception-token-20260101T000000-425.json").write_text(
        json.dumps(
            {
                "matched": True,
                "token": token,
                "rationale_required": True,
                # Fresh, so the 24h window keeps it.
                "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
        ),
        encoding="utf-8",
    )


def test_stop_consumes_the_worktrees_token_markers(layout: DesktopLayout) -> None:
    """IC-11 Option A: Stop consumes the session's markers — in its own tree."""
    worktree_state = layout.worktree / ".claude" / "state"
    main_state = layout.main / ".claude" / "state"
    _write_token_marker(worktree_state, "trivial")
    _write_token_marker(main_state, "trivial")

    result = _run(layout, _CLAUDE_STOP, {"cwd": str(layout.worktree)})

    assert result.returncode == 0, result.stderr
    assert not list(worktree_state.glob("exception-token-*.json"))
    assert list(main_state.glob("exception-token-*.json")), (
        "the worktree session consumed the main checkout's markers"
    )


# ---------------------------------------------------------------------------
# The shared ledger: every harness writes and reads the session's own copy
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("harness", ["claude", "codex", "antigravity"])
def test_prompt_and_summary_use_the_worktrees_ledger(
    layout: DesktopLayout, harness: str
) -> None:
    """UserPromptSubmit writes, and SessionStart reads, the worktree's ledger.

    Main's ledger is pre-populated with the stale state #425 observed being
    injected into every worktree session: it must be neither rewritten nor shown.
    """
    main_ledger = layout.ledger(layout.main)
    _write_ledger(
        main_ledger,
        goal="stale goal from the main checkout",
        workflow={"stage": "executing"},
    )
    main_before = main_ledger.read_text(encoding="utf-8")
    prompt = f"#425 prompt typed in the worktree ({harness})"

    submitted = _run(
        layout,
        _USER_PROMPT_SUBMIT[harness],
        {
            "session_id": "wt-session",
            "cwd": str(layout.worktree),
            "hook_event_name": "UserPromptSubmit",
            "prompt": prompt,
        },
    )
    assert submitted.returncode == 0, submitted.stderr
    assert main_ledger.read_text(encoding="utf-8") == main_before, (
        "the worktree session rewrote the main checkout's ledger"
    )
    worktree_ledger = json.loads(
        layout.ledger(layout.worktree).read_text(encoding="utf-8")
    )
    assert worktree_ledger["last_prompt"] == prompt

    started = _run(
        layout,
        _SESSION_START[harness],
        {
            "session_id": "wt-session",
            "cwd": str(layout.worktree),
            "hook_event_name": "SessionStart",
            "source": "startup",
        },
    )
    assert started.returncode == 0, started.stderr
    assert prompt in started.stdout
    assert "stale goal from the main checkout" not in started.stdout


# ---------------------------------------------------------------------------
# Stop: the completion gate and advisories see the worktree's changes
# ---------------------------------------------------------------------------


def test_stop_hook_reports_the_worktrees_changes(layout: DesktopLayout) -> None:
    """Before #425 the Stop hook ran its git in main, so a worktree session's
    governor-path edit never produced the Pillar 7 Governor Footer reminder, and
    its changed files were recorded into main's ledger."""
    (layout.worktree / "src" / "_core").mkdir(parents=True)
    (layout.worktree / "src" / "_core" / "x.py").write_text("x = 1\n", encoding="utf-8")
    (layout.worktree / "docs" / "ai" / "shared" / "new-rule.md").write_text(
        "# rule\n", encoding="utf-8"
    )

    result = _run(
        layout,
        _CLAUDE_STOP,
        {
            "session_id": "wt-session",
            "cwd": str(layout.worktree),
            "hook_event_name": "Stop",
            "stop_hook_active": False,
        },
    )

    assert result.returncode == 0, result.stderr
    assert "src/_core/x.py" in result.stdout
    assert "[completion-gate] Governor-changing changes detected" in result.stdout
    worktree_ledger = json.loads(
        layout.ledger(layout.worktree).read_text(encoding="utf-8")
    )
    assert worktree_ledger["verification"]["changed_py_files"] == ["src/_core/x.py"]
    assert not layout.ledger(layout.main).exists()


def test_stop_hook_judges_cosmetic_rules_by_the_worktrees_diff(
    layout: DesktopLayout,
) -> None:
    """ADR 047 D4 treats an empty diff as cosmetic. Diffing main — clean — would
    exempt a real rules edit made in the worktree."""
    rules = layout.worktree / _COSMETIC_RULES
    rules.write_text(
        rules.read_text(encoding="utf-8") + "\nNew rule: always run make check.\n",
        encoding="utf-8",
    )

    result = _run(
        layout,
        _CLAUDE_STOP,
        {"session_id": "wt-session", "cwd": str(layout.worktree)},
    )

    assert result.returncode == 0, result.stderr
    assert "[completion-gate] Governor-changing changes detected" in result.stdout


def test_stop_hook_reads_the_worktrees_governor_policy(layout: DesktopLayout) -> None:
    """The policy doc comes from the session's tree, as CI reads the PR's."""
    (layout.main / "docs" / "ai" / "shared" / "governor-paths.md").write_text(
        "# no tiers in this checkout\n", encoding="utf-8"
    )
    (layout.worktree / "docs" / "ai" / "shared" / "new-rule.md").write_text(
        "# rule\n", encoding="utf-8"
    )

    result = _run(
        layout,
        _CLAUDE_STOP,
        {"session_id": "wt-session", "cwd": str(layout.worktree)},
    )

    assert result.returncode == 0, result.stderr
    assert "[completion-gate] Governor-changing changes detected" in result.stdout


@pytest.mark.parametrize("harness", ["codex", "antigravity"])
def test_other_harnesses_refresh_the_worktrees_ledger_on_stop(
    layout: DesktopLayout, harness: str
) -> None:
    """Codex and Antigravity run hooks from the session's own checkout, so only
    the shared ledger is re-rooted there — but it is re-rooted the same way."""
    (layout.worktree / "src").mkdir()
    (layout.worktree / "src" / "x.py").write_text("x = 1\n", encoding="utf-8")

    result = _run(
        layout,
        _STOP[harness],
        {"session_id": "wt-session", "cwd": str(layout.worktree)},
    )

    assert result.returncode == 0, result.stderr
    ledger = json.loads(layout.ledger(layout.worktree).read_text(encoding="utf-8"))
    assert ledger["verification"]["changed_py_files"] == ["src/x.py"]
    assert not layout.ledger(layout.main).exists()


@pytest.mark.parametrize(
    ("argv", "payload"),
    [
        (
            ["sh", _LAUNCHER, ".codex/hooks/post-tool-format.py"],
            {
                "tool_name": "Bash",
                "tool_input": {"command": "pytest -q"},
                "tool_response": {"exit_code": 0},
            },
        ),
        (
            ["sh", _LAUNCHER, ".antigravity/hooks/post-tool-format.py"],
            {
                "tool_name": "run_shell_command",
                "tool_input": {"command": "pytest -q"},
                "exit_code": 0,
            },
        ),
    ],
    ids=["codex", "antigravity"],
)
def test_verification_result_lands_in_the_worktrees_ledger(
    layout: DesktopLayout, argv: list[str], payload: dict[str, object]
) -> None:
    result = _run(layout, argv, {**payload, "cwd": str(layout.worktree)})

    assert result.returncode == 0, result.stderr
    ledger = json.loads(layout.ledger(layout.worktree).read_text(encoding="utf-8"))
    assert ledger["verification"]["status"] == "passed"
    assert not layout.ledger(layout.main).exists()


# ---------------------------------------------------------------------------
# HARNESS_STATE_ROOT still wins for state; classification still follows cwd
# ---------------------------------------------------------------------------


def test_state_override_outranks_a_valid_worktree_cwd(
    layout: DesktopLayout, tmp_path: Path
) -> None:
    """#407's isolation must survive a payload that names a real worktree."""
    override = tmp_path / "override"
    _write_ledger(layout.ledger(override), workflow={"stage": "planned"})
    worktree_state = layout.worktree / ".agents" / "state"
    main_state = layout.main / ".agents" / "state"

    submitted = _run(
        layout,
        _USER_PROMPT_SUBMIT["claude"],
        {"cwd": str(layout.worktree), "prompt": "[trivial] #425 override prompt"},
        state_root=override,
    )
    assert submitted.returncode == 0, submitted.stderr
    ledger = json.loads(layout.ledger(override).read_text(encoding="utf-8"))
    assert ledger["last_prompt"] == "[trivial] #425 override prompt"
    assert list((override / ".claude" / "state").glob("exception-token-*.json"))

    # Classified against the worktree, staged by the override ledger (planned);
    # the [trivial] marker in the override state dir waives the block.
    blocked = _run(
        layout,
        _CLAUDE_STAGE_BLOCK,
        _edit_payload(layout, "src/app/service.py"),
        state_root=override,
    )
    assert blocked.returncode == 0, blocked.stderr
    for marker in (override / ".claude" / "state").glob("exception-token-*.json"):
        marker.unlink()
    blocked = _run(
        layout,
        _CLAUDE_STAGE_BLOCK,
        _edit_payload(layout, "src/app/service.py"),
        state_root=override,
    )
    assert blocked.returncode == 2, blocked.stderr

    assert not worktree_state.exists()
    assert not main_state.exists()
    assert not (layout.worktree / ".claude" / "state").exists()
    assert not (layout.main / ".claude" / "state").exists()


# ---------------------------------------------------------------------------
# A cwd the harness cannot place: touch nothing rather than main's state
# ---------------------------------------------------------------------------


@pytest.fixture
def foreign_repo(tmp_path: Path) -> Path:
    other = tmp_path / "other-repo"
    other.mkdir()
    _git(other, "init", "-q")
    return other.resolve()


@pytest.mark.parametrize("harness", ["claude", "codex", "antigravity"])
def test_a_foreign_cwd_writes_no_ledger(
    layout: DesktopLayout, foreign_repo: Path, harness: str
) -> None:
    """Falling back to the hook's own checkout here would be #425 again."""
    result = _run(
        layout,
        _USER_PROMPT_SUBMIT[harness],
        {"cwd": str(foreign_repo), "prompt": "typed after cd-ing elsewhere"},
    )

    assert result.returncode == 0, result.stderr
    for root in (layout.main, layout.worktree, foreign_repo):
        assert not layout.ledger(root).exists(), root


def test_a_vanished_cwd_neither_blocks_nor_records(layout: DesktopLayout) -> None:
    _write_ledger(layout.ledger(layout.main), workflow={"stage": "planned"})
    payload = {
        **_edit_payload(layout, "src/app/service.py"),
        "cwd": str(layout.main / "deleted-dir"),
    }

    blocked = _run(layout, _CLAUDE_STAGE_BLOCK, payload)
    stopped = _run(layout, _CLAUDE_STOP, payload)

    assert blocked.returncode == 0, blocked.stderr
    assert stopped.returncode == 0, stopped.stderr
    assert stopped.stdout == ""
    assert not layout.ledger(layout.worktree).exists()


# ---------------------------------------------------------------------------
# The resolver itself
# ---------------------------------------------------------------------------


@pytest.fixture
def resolver(layout: DesktopLayout, monkeypatch: pytest.MonkeyPatch):
    """``resolve_session_roots`` as the main copy would run it."""
    import governor.paths as paths  # noqa: PLC0415

    monkeypatch.setattr(paths, "REPO_ROOT", layout.main)
    monkeypatch.delenv("HARNESS_STATE_ROOT", raising=False)
    return paths.resolve_session_roots


def test_resolver_maps_any_cwd_inside_a_worktree_to_its_top_level(
    layout: DesktopLayout, resolver
) -> None:
    nested = layout.worktree / "docs" / "ai"
    roots = resolver({"cwd": str(nested)})
    assert roots.repo_root == layout.worktree
    assert roots.state_root == layout.worktree
    assert not roots.rejected


def test_resolver_accepts_the_main_checkout_itself(
    layout: DesktopLayout, resolver
) -> None:
    roots = resolver({"cwd": str(layout.main)})
    assert roots.repo_root == layout.main


def test_resolver_classifies_worktree_files_as_implementation_source(
    layout: DesktopLayout, resolver
) -> None:
    """The issue's unit-level half: with the session root, a worktree file is
    an implementation edit; against main's root it is under ``.claude/``."""
    from governor.stage_gate import is_implementation_source  # noqa: PLC0415

    edited = str(layout.worktree / "src" / "app" / "service.py")
    roots = resolver({"cwd": str(layout.worktree)})
    assert roots.repo_root is not None
    assert is_implementation_source(edited, roots.repo_root)
    assert not is_implementation_source(edited, layout.main)


@pytest.mark.parametrize(
    "payload",
    [{}, {"cwd": ""}, {"cwd": 7}, None, ["cwd"]],
    ids=["no-cwd", "empty", "not-a-string", "none", "not-a-mapping"],
)
def test_resolver_leaves_a_payload_without_cwd_unrerooted(resolver, payload) -> None:
    roots = resolver(payload)
    assert (roots.repo_root, roots.state_root, roots.rejected) == (None, None, False)


def test_resolver_rejects_cwds_it_cannot_place(
    layout: DesktopLayout, foreign_repo: Path, resolver, tmp_path: Path
) -> None:
    plain_dir = tmp_path / "not-a-repo"
    plain_dir.mkdir()
    for cwd in (
        str(foreign_repo),
        str(plain_dir),
        str(layout.main / "missing"),
        "relative/path",
    ):
        assert resolver({"cwd": cwd}).rejected, cwd


def test_resolver_without_a_repository_keeps_only_its_own_tree(
    layout: DesktopLayout,
    resolver,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A copy that is not in a repository (a downloaded archive) still serves a
    session working inside it — every hook going silent would be a regression —
    but answers for nothing else."""
    import governor.paths as paths  # noqa: PLC0415

    loose = tmp_path / "loose-copy"
    (loose / "src").mkdir(parents=True)
    monkeypatch.setattr(paths, "REPO_ROOT", loose)

    for cwd in (loose, loose / "src"):
        roots = resolver({"cwd": str(cwd)})
        assert (roots.repo_root, roots.state_root, roots.rejected) == (
            None,
            None,
            False,
        )
    assert resolver({"cwd": str(layout.worktree)}).rejected


def test_resolver_without_git_refuses_a_nested_worktree(
    layout: DesktopLayout, resolver, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No git to ask: the worktree's own ``.git`` file still marks it as a tree
    main's copy must not answer for — the fallback is not #425 again."""
    import governor.paths as paths  # noqa: PLC0415

    monkeypatch.setattr(paths.shutil, "which", lambda _name: None)

    assert not resolver({"cwd": str(layout.main / "docs")}).rejected
    assert resolver({"cwd": str(layout.worktree)}).rejected
    assert resolver({"cwd": str(layout.worktree / "docs" / "ai")}).rejected
    assert resolver({"cwd": "/"}).rejected


def test_resolver_turns_an_unexpected_error_into_a_rejection(
    layout: DesktopLayout, resolver, monkeypatch: pytest.MonkeyPatch
) -> None:
    import governor.paths as paths  # noqa: PLC0415

    def broken(*_args: object) -> list[str] | None:
        raise UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid start byte")

    monkeypatch.setattr(paths, "_rev_parse", broken)
    assert resolver({"cwd": str(layout.worktree)}).rejected
    assert resolver({"cwd": "/bad\x00path"}).rejected


@pytest.mark.parametrize(
    ("stdin", "expected"),
    [
        ("", "none"),
        ("{}", "none"),
        ('{"cwd": "/"}', "rejected"),
        ("not json", "rejected"),
        (None, "<worktree>"),
    ],
    ids=["empty", "no-cwd", "foreign", "garbage", "worktree"],
)
def test_session_root_cli_always_answers(
    layout: DesktopLayout, stdin: str | None, expected: str
) -> None:
    """The Stop shell treats *no* answer as "the resolver never ran"."""
    payload = json.dumps({"cwd": str(layout.worktree)}) if stdin is None else stdin
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-m", "governor.session_root_cli"],
        cwd=layout.main,
        input=payload,
        env={
            **{k: v for k, v in os.environ.items() if k != "HARNESS_STATE_ROOT"},
            "PYTHONPATH": str(layout.main / ".agents" / "shared"),
        },
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    want = str(layout.worktree) if expected == "<worktree>" else expected
    assert result.stdout.strip() == want


def _break_session_root_cli(root: Path) -> None:
    """Make the resolver CLI unanswerable, as a missing interpreter would."""
    (root / ".agents" / "shared" / "governor" / "session_root_cli.py").unlink()


def test_stop_skips_when_the_resolver_cannot_place_a_worktree(
    layout: DesktopLayout,
) -> None:
    """No answer and a cwd in a nested checkout: skip, say so, touch nothing."""
    _break_session_root_cli(layout.main)
    _write_token_marker(layout.main / ".claude" / "state", "trivial")

    result = _run(layout, _CLAUDE_STOP, {"cwd": str(layout.worktree)})

    assert result.returncode == 0, result.stderr
    assert "Stop checks skipped" in result.stdout
    assert not layout.ledger(layout.main).exists()
    assert list((layout.main / ".claude" / "state").glob("exception-token-*.json"))


@pytest.mark.parametrize("payload_cwd", ["main", "none"])
def test_stop_without_a_resolver_still_serves_its_own_checkout(
    layout: DesktopLayout, payload_cwd: str
) -> None:
    """No answer must not silence an ordinary session in this checkout: a cwd
    inside it, or a payload with no cwd, keeps the pre-#425 Stop."""
    _break_session_root_cli(layout.main)
    (layout.main / "src" / "_core").mkdir(parents=True)
    (layout.main / "src" / "_core" / "x.py").write_text("x = 1\n", encoding="utf-8")
    payload: dict[str, object] = (
        {"cwd": str(layout.main / "src")} if payload_cwd == "main" else {}
    )

    result = _run(layout, _CLAUDE_STOP, payload)

    assert result.returncode == 0, result.stderr
    assert "src/_core/x.py" in result.stdout
    assert "Stop checks skipped" not in result.stdout


@pytest.mark.parametrize("resolver", ["answers", "missing"])
def test_stop_in_a_downloaded_archive_keeps_working(
    tmp_path: Path, resolver: str
) -> None:
    """A copy with no repository at all — a ZIP download — is its own session's
    tree, with or without the resolver CLI."""
    archive = tmp_path / "archive"
    for rel in _COPIED_DIRS:
        shutil.copytree(
            _REPO_ROOT / rel,
            archive / rel,
            ignore=shutil.ignore_patterns("__pycache__", "state"),
        )
    (archive / "pyproject.toml").write_text(
        '[project]\nname = "archive"\nversion = "0"\n', encoding="utf-8"
    )
    if resolver == "missing":
        _break_session_root_cli(archive)
    layout = DesktopLayout(main=archive.resolve(), worktree=archive.resolve())

    result = _run(layout, _CLAUDE_STOP, {"cwd": str(archive)})

    assert result.returncode == 0, result.stderr
    assert "Stop checks skipped" not in result.stdout
    assert layout.ledger(archive).exists(), "the Stop ledger refresh did not run"


def test_resolver_keeps_state_on_the_override(
    layout: DesktopLayout, resolver, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("HARNESS_STATE_ROOT", str(tmp_path / "override"))
    roots = resolver({"cwd": str(layout.worktree)})
    assert roots.repo_root == layout.worktree
    assert roots.state_root is None


def test_pr_lookup_runs_gh_in_the_given_tree(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """``gh`` reads the branch from its working directory — the session's tree."""
    import governor.completion_gate as gate  # noqa: PLC0415

    seen: list[object] = []

    def fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        seen.append(kwargs.get("cwd"))
        return subprocess.CompletedProcess(["gh"], 0, stdout='{"number": 425}')

    monkeypatch.setattr(gate.subprocess, "run", fake_run)

    assert gate.pr_number_from_branch(tmp_path) == 425
    assert gate.pr_number_from_branch() == 425
    assert seen == [tmp_path, None]


def test_state_override_owns_stop_marker_consumption_after_log_retirement(
    layout: DesktopLayout, tmp_path: Path
) -> None:
    """Retiring command logs must not weaken override-scoped token cleanup."""
    override = tmp_path / "override"
    for root in (layout.main, layout.worktree, override):
        _write_token_marker(root / ".claude/state", "trivial")
    stopped = _run(
        layout,
        _CLAUDE_STOP,
        {"session_id": "wt-session", "cwd": str(layout.worktree)},
        state_root=override,
    )
    assert stopped.returncode == 0, stopped.stderr
    assert not list((override / ".claude/state").glob("exception-token-*.json"))
    for root in (layout.main, layout.worktree):
        assert list((root / ".claude/state").glob("exception-token-*.json")), root


@pytest.mark.parametrize("harness", ["codex", "antigravity"])
@pytest.mark.parametrize(
    "command,result_data,expected",
    [
        ("rg pytest docs/", {"exit_code": 0}, "pending"),
        ("unrecognized-command", {"exit_code": 0}, "pending"),
        ("pytest -q", {}, "pending"),
        ("pytest -q", {"exit_code": 1}, "failed"),
    ],
)
def test_real_outcome_recorder_rejects_names_and_unknown_results(
    layout: DesktopLayout, harness: str, command: str, result_data: dict, expected: str
) -> None:
    target = layout.ledger(layout.worktree)
    _write_ledger(
        target, verification={"status": "pending", "changed_py_files": ["src/a.py"]}
    )
    before = target.read_bytes()
    payload = {
        "cwd": str(layout.worktree),
        "tool_name": "Bash" if harness == "codex" else "run_shell_command",
        "tool_input": {"command": command},
        **result_data,
    }
    result = _run(
        layout, ["sh", _LAUNCHER, f".{harness}/hooks/post-tool-format.py"], payload
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(target.read_text())["verification"]["status"] == expected
    if expected == "pending":
        assert target.read_bytes() == before
    assert not layout.ledger(layout.main).exists()
    assert not list(layout.worktree.glob(".*/state/verify-log-*.json"))


def test_real_gemini_cancel_does_not_record_a_verify_verdict(
    layout: DesktopLayout,
) -> None:
    target = layout.ledger(layout.worktree)
    _write_ledger(
        target, verification={"status": "pending", "changed_py_files": ["src/a.py"]}
    )
    before = target.read_bytes()
    result = _run(
        layout,
        ["sh", _LAUNCHER, ".antigravity/hooks/post-tool-format.py"],
        {
            "cwd": str(layout.worktree),
            "tool_name": "run_shell_command",
            "tool_input": {"command": "pytest -q"},
            "tool_response": {
                "error": {"message": "Operation cancelled by user."},
                "llmContent": "Output: partial",
            },
        },
    )
    assert result.returncode == 0, result.stderr
    assert target.read_bytes() == before
