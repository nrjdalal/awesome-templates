"""Guard: a pytest session must never write the operator's live harness state.

Issue #407. The harness hooks resolve their state directory from
``HARNESS_STATE_ROOT`` and **default to the real repository root**
(``.agents/shared/work_ledger.py``, and ten sibling hook modules). Isolation is
therefore opt-in per call site, and a test that forgets it silently rewrites
``.agents/state/current-work.json`` — the file the ``SessionStart`` hook reads
back as session context. In #407 a fixture prompt carrying a ``[trivial]``
exception token landed there and was read, in a later session, as a
process-gate waiver nobody issued.

Eight call sites did opt in. Five files did not, by two distinct mechanisms:

* **inherited environment** — ``subprocess.run`` with no ``env=`` hands the
  child ``os.environ``, so an unset ``HARNESS_STATE_ROOT`` reaches the hook
  (``test_token_parser.py``, ``test_shared_module_parity.py``,
  ``test_locale.py``, ``tests/integration/test_stop_hook_e2e.py``);
* **in-process import** — a hook module exec'd inside pytest via ``importlib``
  writes through ``work_ledger`` in *this* process (``test_fail_open.py``).

The fix makes isolation the session default (``tests/conftest.py``) rather than
a per-call-site obligation, because a per-call fix protects the sites that
exist today and nothing else. These tests pin that default from both ends: the
environment the session runs under, and the behaviour of a deliberately naive
subprocess helper.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_LIVE_LEDGER = _REPO_ROOT / ".agents" / "state" / "current-work.json"
_CODEX_UPS_HOOK = _REPO_ROOT / ".codex" / "hooks" / "user-prompt-submit.py"
_SHARED_DIR = _REPO_ROOT / ".agents" / "shared"


def _live_ledger_fingerprint() -> str | None:
    """Exact bytes of the live ledger, or ``None`` when it does not exist."""
    try:
        return _LIVE_LEDGER.read_text(encoding="utf-8")
    except OSError:
        return None


# ---------------------------------------------------------------------------
# The session default itself
# ---------------------------------------------------------------------------


def test_harness_state_root_is_set_and_not_the_repo() -> None:
    """``tests/conftest.py`` must redirect harness state away from the repo."""
    raw = os.environ.get("HARNESS_STATE_ROOT")
    assert raw, (
        "HARNESS_STATE_ROOT is unset for this pytest session, so every harness "
        "hook a test spawns writes the real .agents/ and .codex/ state dirs. "
        "tests/conftest.py is supposed to set it (#407)."
    )
    assert Path(raw).resolve() != _REPO_ROOT.resolve(), (
        f"HARNESS_STATE_ROOT points at the repository itself ({raw}); "
        "harness state written by tests would be the operator's live state."
    )


def test_in_process_work_ledger_resolves_outside_the_repo() -> None:
    """The in-process leak path: ``work_ledger`` binds its paths at import.

    ``STATE_ROOT`` is a module-level constant, so a test that exec's a hook
    inside the pytest process (``test_fail_open.py``) writes wherever
    ``work_ledger`` resolved on *first* import. Setting the variable in a
    fixture would be too late; setting it in ``tests/conftest.py`` at module
    scope is early enough, and this asserts that it was.
    """
    if str(_SHARED_DIR) not in sys.path:
        sys.path.insert(0, str(_SHARED_DIR))
    import work_ledger  # noqa: PLC0415

    assert work_ledger.LEDGER_PATH.resolve() != _LIVE_LEDGER.resolve(), (
        "work_ledger resolved to the live ledger "
        f"({work_ledger.LEDGER_PATH}); an in-process hook exec would overwrite "
        "the operator's prompt."
    )


# ---------------------------------------------------------------------------
# Behaviour: the naive helper shape must be safe by default
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not _CODEX_UPS_HOOK.exists(), reason="Codex UserPromptSubmit hook not present"
)
def test_environ_inheriting_hook_subprocess_leaves_live_ledger_untouched() -> None:
    """Spawn a real hook the way an un-isolated helper does, and prove it.

    This deliberately reproduces the #407 call shape — ``subprocess.run`` with
    no ``env=``, so the child inherits ``os.environ`` — with a prompt that
    drives the hook down its ``update_last_prompt`` path. Passing an explicit
    isolated ``env`` here would test the fix's *workaround* rather than its
    default, and would stay green if the session default were removed.
    """
    before = _live_ledger_fingerprint()
    marker = "#407 guard prompt — must never reach the live ledger"

    result = subprocess.run(  # noqa: S603
        [sys.executable, str(_CODEX_UPS_HOOK)],
        input=json.dumps({"prompt": f"[trivial] {marker}"}),
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr

    after = _live_ledger_fingerprint()
    if before is None:
        assert after is None, (
            "The hook created the live ledger at "
            f"{_LIVE_LEDGER} during a test run (#407)."
        )
    else:
        assert after == before, (
            f"The live ledger at {_LIVE_LEDGER} was rewritten by a test-spawned "
            "hook (#407). HARNESS_STATE_ROOT did not reach the child process."
        )
        assert marker not in (after or ""), (
            "A test fixture prompt is now stored as the operator's last_prompt."
        )
