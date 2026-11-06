"""Risk floors and Git parsing must not hide sensitive or renamed changes."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))
spec = importlib.util.spec_from_file_location(
    "review_packet", ROOT / "tools/review_packet.py"
)
assert spec is not None and spec.loader is not None
loaded = importlib.util.module_from_spec(spec)
sys.modules["review_packet"] = loaded
spec.loader.exec_module(loaded)
Change = loaded.Change
packet = loaded.packet
read_changes = loaded.read_changes


def test_size_boundary_cannot_reduce_path_risk():
    assert packet([Change("README.md", 200, 200)])["risk"] == "low"
    assert packet([Change("README.md", 201, 200)])["risk"] == "medium"
    for path in (
        "AGENTS.md",
        "src/user/auth.py",
        "migrations/0001.py",
        ".github/workflows/ci.yml",
        "src/a/interface/server/schemas/request.py",
    ):
        assert packet([Change(path, 1, 0)])["risk"] == "high"
    assert packet([Change("src/user/service.py", 1, 0)])["risk"] == "medium"
    assert packet([Change("unknown.conf", 1, 0)])["risk"] == "medium"


def test_binary_is_high_and_size_is_incomplete():
    result = packet([Change("docs/demo.png", None, None)])
    assert result["risk"] == "high"
    assert result["size_complete"] is False
    assert result["verification"] == "not run by this command"


def test_risk_ranks_paths_before_alphabetical_order():
    result = packet([Change("README.md", 1, 0), Change("migrations/z.py", 1, 0)])
    assert result["files"][0]["path"] == "migrations/z.py"


def test_rename_reads_both_paths_and_preserves_unusual_names(tmp_path):
    def git(*args):
        return subprocess.run(
            ["git", *args], cwd=tmp_path, check=True, capture_output=True
        )

    git("init")
    git("config", "user.email", "test@example.invalid")
    git("config", "user.name", "Test")
    source = tmp_path / "auth.py"
    source.write_text("safe = True\n")
    git("add", ".")
    git("commit", "-m", "initial")
    source.rename(tmp_path / "new\tname\n.py")
    git("add", "-A")
    changes = read_changes("HEAD", tmp_path)
    assert {item.path for item in changes} == {"auth.py", "new\tname\n.py"}
    assert packet(changes)["risk"] == "high"


def test_diverged_base_excludes_unrelated_commits_but_includes_staged_and_working_changes(
    tmp_path,
):
    def git(*args):
        return subprocess.run(
            ["git", *args], cwd=tmp_path, check=True, capture_output=True
        )

    git("init")
    git("config", "user.email", "test@example.invalid")
    git("config", "user.name", "Test")
    (tmp_path / "README.md").write_text("initial\n")
    (tmp_path / "notes.txt").write_text("initial\n")
    git("add", ".")
    git("commit", "-m", "common base")
    git("branch", "base")
    (tmp_path / "own.md").write_text("ticket commit\n")
    git("add", ".")
    git("commit", "-m", "ticket work")
    ticket_head = git("rev-parse", "HEAD").stdout.decode().strip()
    git("switch", "base")
    (tmp_path / "auth.py").write_text("unrelated base-only code\n")
    git("add", ".")
    git("commit", "-m", "unrelated base advance")
    git("checkout", "--detach", ticket_head)
    (tmp_path / "README.md").write_text("staged change\n")
    git("add", "README.md")
    (tmp_path / "notes.txt").write_text("unstaged change\n")
    changes = read_changes("base", tmp_path)
    assert {item.path for item in changes} == {"own.md", "README.md", "notes.txt"}
    assert sum(item.added + item.deleted for item in changes) == 5
    assert packet(changes)["risk"] == "low"
