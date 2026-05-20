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
"""

from __future__ import annotations

import shutil
import subprocess
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
