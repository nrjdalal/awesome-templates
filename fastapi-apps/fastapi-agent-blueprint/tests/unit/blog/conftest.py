"""Provide the post-copy ``src.author`` / ``src.post`` layout for blog tests.

The blog example teaches the real cross-domain pattern (``src/auth -> src/user``):
``post`` imports ``author`` via absolute ``src.author.*`` paths, which only
resolve after the documented activation step (``cp -r examples/blog/author
src/author``, same for ``post``). Unit tests import the service modules at
pytest COLLECTION time — before any fixture runs — so this conftest builds the
copied layout at module import time: it copies both example domains into a
temp directory and extends ``src.__path__`` with it, making ``src.author`` /
``src.post`` importable while every ``src._core.*`` module keeps resolving
from the repo (identical class objects, no dual registration).

The temp directory is removed at interpreter exit; no teardown is needed —
nothing outside ``tests/unit/blog`` imports these packages, and
``discover_domains()`` scans the real ``src/`` directory on disk, so the
shadow never leaks into e2e app boots in the same session.
"""

import atexit
import shutil
import tempfile
from pathlib import Path

import src

_REPO_ROOT = Path(__file__).resolve().parents[3]
_BLOG_EXAMPLE = _REPO_ROOT / "examples" / "blog"

_shadow_root = Path(tempfile.mkdtemp(prefix="blog_src_shadow_"))
atexit.register(shutil.rmtree, _shadow_root, ignore_errors=True)

for _domain in ("author", "post"):
    shutil.copytree(
        _BLOG_EXAMPLE / _domain,
        _shadow_root / _domain,
        ignore=shutil.ignore_patterns("__pycache__"),
    )

if str(_shadow_root) not in src.__path__:
    src.__path__.append(str(_shadow_root))
