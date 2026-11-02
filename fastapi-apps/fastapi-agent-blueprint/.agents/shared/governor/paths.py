"""Governor path discovery (IC-10).

Provides ``REPO_ROOT`` and ``GOVERNOR_PATHS_MD`` for shared governor
modules. Hook scripts may rely on the same constants when they need to
resolve repo-relative locations without re-implementing discovery.

Resolution strategy:
    1. Walk parents from this file looking for a ``.git`` directory.
    2. Fall back to ``git rev-parse --show-toplevel`` so checkouts via
       worktrees or unusual layouts still resolve correctly.
    3. Final fallback: parents[3] from this file (matches the on-disk
       layout ``<repo>/.agents/shared/governor/paths.py``).

``REPO_ROOT`` is the checkout whose harness code is *running*, which is not
always the tree the session works on — see ``resolve_session_roots`` (#425).
"""

from __future__ import annotations

import os
import shutil
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path


def _discover_repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in (here, *here.parents):
        if (parent / ".git").exists():
            return parent

    git = shutil.which("git")
    if git is not None:
        try:
            result = subprocess.run(  # noqa: S603 — git resolved via shutil.which, args fixed
                [git, "rev-parse", "--show-toplevel"],
                capture_output=True,
                text=True,
                check=False,
                timeout=5,
            )
            top = result.stdout.strip()
            if result.returncode == 0 and top:
                return Path(top)
        except (OSError, subprocess.TimeoutExpired):
            pass

    return here.parents[3]


REPO_ROOT: Path = _discover_repo_root()
GOVERNOR_PATHS_MD: Path = REPO_ROOT / "docs" / "ai" / "shared" / "governor-paths.md"


@dataclass(frozen=True)
class SessionRoots:
    """Where one hook invocation should look, re-rooted onto the session (#425).

    Three outcomes, kept apart on purpose:

    * **re-rooted** — ``repo_root`` is the session's tree. ``state_root`` is
      that tree too, unless ``HARNESS_STATE_ROOT`` is set (then ``None``).
    * **not re-rooted** — the payload has no ``cwd``; both fields are ``None``
      and the caller keeps its own file-relative defaults (``REPO_ROOT``,
      ``STATE_ROOT``, ``STATE_DIR``, ``work_ledger.LEDGER_PATH``), which is
      the pre-#425 behaviour and what tests monkeypatch.
    * **rejected** — the payload names a ``cwd`` this harness cannot place
      (another repository, a vanished directory, a git failure). Falling back
      to the defaults there would write this checkout's state for some other
      tree's session — the bug itself — so callers skip session-scoped reads
      and writes instead. Skipping is the fail-open direction: a gate allows,
      a ledger update does not happen.
    """

    repo_root: Path | None = None
    state_root: Path | None = None
    rejected: bool = False

    def state_dir(self, harness: str, default: Path) -> Path:
        """``<state root>/<harness>/state``, or ``default`` when not re-rooted."""

        return (
            default if self.state_root is None else self.state_root / harness / "state"
        )


def _rev_parse(git: str, cwd: Path, *args: str) -> list[str] | None:
    try:
        result = subprocess.run(  # noqa: S603 — git resolved via shutil.which, args fixed
            [git, "-C", str(cwd), "rev-parse", *args],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    lines = result.stdout.splitlines()
    if result.returncode != 0 or len(lines) != len(args):
        return None
    return lines


def _absolute(base: Path, reported: str) -> Path:
    # `--git-common-dir` may answer relative to `-C` (".git" at a main checkout).
    path = Path(reported)
    return (path if path.is_absolute() else base / path).resolve()


def _inside_this_checkout(here: Path) -> bool:
    """``here`` is this checkout, or a directory of it outside any nested one.

    The no-git fallback: a ``.git`` entry between ``here`` and ``REPO_ROOT``
    marks a nested checkout — a linked worktree under ``.claude/worktrees/``
    has a ``.git`` file at its root — which is exactly the tree this copy must
    not answer for.
    """

    root = REPO_ROOT.resolve()
    node = here.resolve()
    depth = len(node.relative_to(root).parts)  # ValueError when outside
    for _ in range(depth):
        if (node / ".git").exists():
            return False
        node = node.parent
    return True


def resolve_session_roots(payload: object) -> SessionRoots:
    """Re-root a hook onto the working tree named by its payload's ``cwd``.

    Hooks used to take every root from their own file location, so whichever
    checkout's copy ran decided the session's ledger, state dirs, git tree and
    implementation surface. Claude Code desktop runs a worktree session's hooks
    from the main checkout (``--project-config-root``), where the process cwd
    and ``CLAUDE_PROJECT_DIR`` both name main; the payload ``cwd`` is the one
    input that names the worktree, and Claude, Codex and Gemini all send it.

    The ``cwd`` is accepted only when it lies in a working tree of the *same*
    repository as this code (equal ``--git-common-dir``). ``cwd`` follows a
    ``cd``, so without that check a session that wandered into an unrelated or
    sibling checkout would start writing this harness's state there; such a
    ``cwd`` is *rejected* (see ``SessionRoots``).

    Only a payload with no ``cwd`` keeps the caller's defaults unconditionally.
    When git cannot answer — no ``git``, or this copy is not in a repository (a
    downloaded archive) — the defaults are kept only if the ``cwd`` is
    demonstrably inside this checkout; anything else is rejected. Never raises:
    an unexpected error with a ``cwd`` in hand is a rejection (HC-5.5).
    """

    cwd = payload.get("cwd") if isinstance(payload, Mapping) else None
    if not isinstance(cwd, str) or not cwd:
        return SessionRoots()
    try:
        here = Path(cwd)
        if not here.is_absolute() or not here.is_dir():
            return SessionRoots(rejected=True)
        git = shutil.which("git")
        own = _rev_parse(git, REPO_ROOT, "--git-common-dir") if git else None
        if git is None or own is None:
            inside = _inside_this_checkout(here)
            return SessionRoots() if inside else SessionRoots(rejected=True)
        session = _rev_parse(git, here, "--show-toplevel", "--git-common-dir")
        if session is None:
            return SessionRoots(rejected=True)
        if _absolute(here, session[1]) != _absolute(REPO_ROOT, own[0]):
            return SessionRoots(rejected=True)
        tree = Path(session[0]).resolve()
    except Exception:  # noqa: BLE001 — a resolver must never take a hook down
        return SessionRoots(rejected=True)
    # HARNESS_STATE_ROOT outranks the session for *state* only: tests rely on it
    # (#407), and every hook's default STATE_ROOT already honours it, so the
    # state root stays un-rerooted. Classification and git still follow the tree.
    override = os.environ.get("HARNESS_STATE_ROOT")
    return SessionRoots(repo_root=tree, state_root=None if override else tree)
