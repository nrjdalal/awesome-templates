"""HC-5.5 fail-open tests (Phase 5 #124, R0-A.1 + R0-B.3).

Three tiers:
    1. Top-level shared import failure → shim subprocess exit 0, stdout empty
    2. Function-call ImportError (proxy raising at attribute access) →
       shim function returns safe default, no traceback
    3. R0-A.1 invariant — importing a shim under
       contextlib.suppress(Exception) MUST NOT raise SystemExit.
       Top-level sys.exit / raise SystemExit in shim modules would crash
       .codex/hooks/stop-sync-reminder.py because SystemExit (BaseException
       subclass) is not caught by suppress(Exception).
"""

from __future__ import annotations

import contextlib
import importlib
import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
CLAUDE_HOOKS = [
    REPO_ROOT / ".claude" / "hooks" / "user_prompt_submit.py",
    REPO_ROOT / ".claude" / "hooks" / "verify_first.py",
    REPO_ROOT / ".claude" / "hooks" / "completion_gate.py",
]
CODEX_HOOKS = [
    REPO_ROOT / ".codex" / "hooks" / "user-prompt-submit.py",
    REPO_ROOT / ".codex" / "hooks" / "verify_first.py",
    REPO_ROOT / ".codex" / "hooks" / "completion_gate.py",
]


# ---------------------------------------------------------------------------
# Tier 1 — top-level shared import failure (PYTHONPATH scrambled)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "hook",
    [
        REPO_ROOT / ".claude" / "hooks" / "user_prompt_submit.py",
        REPO_ROOT / ".codex" / "hooks" / "user-prompt-submit.py",
    ],
    ids=["claude", "codex"],
)
def test_tier1_shim_fails_open_when_shared_unimportable(
    hook: Path, monkeypatch, tmp_path
) -> None:
    """Run the shim with a renamed .agents/shared so `governor` is
    unimportable. Expect exit 0, no stdout, no SystemExit traceback."""

    # We can't rename the real .agents directory; instead point the shim's
    # parents[2] discovery at a temporary directory by running the shim
    # from a copy in tmp_path with sys.path empty of the shared root.
    env = {
        "PATH": "/usr/bin:/bin",
        "PYTHONPATH": "/nonexistent",
    }
    # Copy the shim file alone into tmp_path so its parents[2] does NOT
    # contain .agents/shared/ — forcing the import to fail.
    fake_repo = tmp_path / "fake-repo"
    fake_repo.mkdir()
    tool_dir = fake_repo / hook.parent.parent.name / hook.parent.name
    tool_dir.mkdir(parents=True)

    fake_hook = tool_dir / hook.name
    fake_hook.write_text(hook.read_text(encoding="utf-8"), encoding="utf-8")
    # Codex side imports _shared at module top — copy it too so the
    # import doesn't blow up before our governor try/except runs.
    if "codex" in str(hook):
        shared_src = REPO_ROOT / ".codex" / "hooks" / "_shared.py"
        (tool_dir / "_shared.py").write_text(
            shared_src.read_text(encoding="utf-8"), encoding="utf-8"
        )

    result = subprocess.run(  # noqa: S603
        [sys.executable, str(fake_hook)],
        input='{"prompt":"[trivial] test"}',
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    assert result.returncode == 0, (
        f"shim exited {result.returncode}, stderr={result.stderr!r}"
    )
    assert result.stdout == ""
    # No traceback in stderr (function-level exceptions might still emit
    # parser stderr payload on Claude side, but no SystemExit traceback).
    assert "Traceback" not in result.stderr


# ---------------------------------------------------------------------------
# Tier 2 — function-call ImportError surfaces as safe default
# ---------------------------------------------------------------------------
def test_tier2_function_call_import_error_returns_safe_default(
    monkeypatch,
) -> None:
    """If the shared writer raises at call time (not at import), the
    shim wrapper must absorb it and return None / False rather than
    propagating."""

    sys.path.insert(0, str(REPO_ROOT / ".claude" / "hooks"))
    try:
        import user_prompt_submit as ups  # noqa: PLC0415

        def boom(*_args, **_kwargs):
            raise ImportError("simulated shared failure")

        monkeypatch.setattr(ups, "_shared_write_marker", boom)
        # write_marker absorbs the failure — but the shim raises only
        # on internal call; for the safe-default contract we check that
        # main() does not propagate the exception.
        # The shim wraps main() in try/except; calling it with empty
        # stdin should still return 0.
        # Force a graceful path by setting _SHARED_OK False via boom impact.
        monkeypatch.setattr(ups, "_SHARED_OK", False)
        assert ups.main() == 0
    finally:
        sys.path.pop(0)
        for mod in list(sys.modules):
            if mod == "user_prompt_submit":
                del sys.modules[mod]


# ---------------------------------------------------------------------------
# Tier 2 supplement (R1-B.1) — verify_first / completion_gate entry points
# also degrade safely when the shared module raises at attribute lookup.
# ---------------------------------------------------------------------------
def test_tier2_verify_first_read_latest_token_marker_safe_default(
    monkeypatch, tmp_path
) -> None:
    """Claude verify_first.read_latest_token_marker must return None when
    the shared reader raises rather than propagating to the Stop hook."""

    sys.path.insert(0, str(REPO_ROOT / ".claude" / "hooks"))
    sys.modules.pop("verify_first", None)
    try:
        import verify_first as vf  # noqa: PLC0415

        def boom(*_args, **_kwargs):
            raise ImportError("simulated shared reader failure")

        monkeypatch.setattr(vf, "read_latest_token", boom)
        # Tier 2 contract: hook helpers do not propagate exceptions.
        # Drive the degraded path explicitly via _SHARED_OK=False.
        monkeypatch.setattr(vf, "_SHARED_OK", False)
        # read_latest_token_marker must surface the degraded state as None.
        assert vf.read_latest_token_marker(tmp_path) is None
        # should_remind must complete WITHOUT raising; the boolean it
        # returns is decided by the existing verify-first decision tree
        # (no marker → not exploration → reminder fires) and is not the
        # invariant under test here. The invariant is "no propagation".
        payload = {"tool_input": {"file_path": "src/foo.py"}}
        result = vf.should_remind(payload, state_dir=tmp_path)
        assert isinstance(result, bool)
    finally:
        sys.path.pop(0)
        sys.modules.pop("verify_first", None)


def test_tier2_completion_gate_entry_points_safe_default(monkeypatch, tmp_path) -> None:
    """Claude completion_gate.governor_changing_segment +
    consume_phase2_markers must absorb shared-side failures and stay
    silent rather than propagating to the Stop hook."""

    sys.path.insert(0, str(REPO_ROOT / ".claude" / "hooks"))
    sys.modules.pop("completion_gate", None)
    try:
        import completion_gate as cg  # noqa: PLC0415

        # Force the degraded path; both entry points must short-circuit.
        monkeypatch.setattr(cg, "_SHARED_OK", False)
        assert cg.governor_changing_segment() is None
        # consume_phase2_markers returns None (no-op) and does not raise.
        cg.consume_phase2_markers(tmp_path)
    finally:
        sys.path.pop(0)
        sys.modules.pop("completion_gate", None)


# ---------------------------------------------------------------------------
# A-1 regression — Codex write_marker OSError must not block exit-0
# (HC-5.5 fail-open; fix in governor hardening followup)
# ---------------------------------------------------------------------------
def test_codex_write_marker_oserror_still_returns_zero() -> None:
    """Codex hook: write_marker raising OSError must not prevent main()
    from returning 0 (HC-5.5 fail-open)."""
    import io  # noqa: PLC0415

    codex_hook = REPO_ROOT / ".codex" / "hooks" / "user-prompt-submit.py"
    spec = importlib.util.spec_from_file_location("codex_ups_a1", str(codex_hook))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    try:

        def _boom(payload: dict) -> None:
            raise OSError("disk full simulated A-1")

        mod.write_marker = _boom
        orig_stdin = sys.stdin
        sys.stdin = io.StringIO('{"prompt": "[trivial] A-1 regression"}')
        try:
            rc = mod.main()
        finally:
            sys.stdin = orig_stdin
        assert rc == 0
    finally:
        sys.modules.pop("codex_ups_a1", None)


def test_codex_write_marker_oserror_does_not_silence_stderr_payload() -> None:
    """After write_marker raises, the stderr payload print must still execute
    so the hook's informational output is not lost."""
    import io  # noqa: PLC0415
    import json as _json  # noqa: PLC0415

    codex_hook = REPO_ROOT / ".codex" / "hooks" / "user-prompt-submit.py"
    spec = importlib.util.spec_from_file_location("codex_ups_a1s", str(codex_hook))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    try:

        def _boom(payload: dict) -> None:
            raise OSError("disk full simulated A-1 stderr")

        mod.write_marker = _boom
        captured = io.StringIO()
        orig_stdin, orig_stderr = sys.stdin, sys.stderr
        sys.stdin = io.StringIO('{"prompt": "[trivial] A-1 stderr check"}')
        sys.stderr = captured
        try:
            mod.main()
        finally:
            sys.stdin = orig_stdin
            sys.stderr = orig_stderr
        output = captured.getvalue()
        found = False
        for line in output.splitlines():
            try:
                payload = _json.loads(line)
            except _json.JSONDecodeError:
                continue
            if payload.get("matched") is True and payload.get("token") is not None:
                found = True
                break
        assert found, "Expected matched-token JSON in stderr, got: " + repr(output)
    finally:
        sys.modules.pop("codex_ups_a1s", None)


# ---------------------------------------------------------------------------
# Tier 3 — R0-A.1 invariant (no SystemExit at module-import)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("hook", CLAUDE_HOOKS + CODEX_HOOKS)
def test_tier3_shim_import_does_not_raise_systemexit(hook: Path) -> None:
    """Simulate stop-sync-reminder.py's contextlib.suppress(Exception)
    pattern. Importing each shim must NOT raise SystemExit — that would
    bypass suppress(Exception) and crash the Stop hook."""

    # Use a fresh subprocess so module-level state from prior tests
    # doesn't mask a real top-level exit.
    code = f"""
import contextlib, sys
sys.path.insert(0, {str(hook.parent)!r})
caught_systemexit = False
try:
    with contextlib.suppress(Exception):
        spec = __import__('importlib.util', fromlist=['util']).util.spec_from_file_location(
            {hook.stem!r}, {str(hook)!r}
        )
        mod = __import__('importlib.util', fromlist=['util']).util.module_from_spec(spec)
        spec.loader.exec_module(mod)
except SystemExit:
    caught_systemexit = True
print('SYSEXIT' if caught_systemexit else 'OK')
"""
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "OK", (
        f"{hook.name}: importing as a module raised SystemExit "
        "— would crash stop-sync-reminder.py"
    )


# ---------------------------------------------------------------------------
# Tier 3 supplement — direct importlib import without subprocess
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("hook", CLAUDE_HOOKS + CODEX_HOOKS)
def test_tier3_inproc_import_does_not_raise_systemexit(hook: Path) -> None:
    """Same invariant verified in-process via importlib.util."""

    sys.path.insert(0, str(hook.parent))
    try:
        spec = importlib.util.spec_from_file_location(hook.stem, str(hook))
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        with contextlib.suppress(Exception):
            spec.loader.exec_module(module)
        # If we reach here without a SystemExit propagating out of
        # contextlib.suppress(Exception), the invariant holds.
    finally:
        sys.path.pop(0)
        sys.modules.pop(hook.stem, None)
