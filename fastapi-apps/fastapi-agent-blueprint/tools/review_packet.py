"""Report a review-risk floor for a tracked diff; never claim checks were run."""

from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath

from check_governor_footer import _is_governor_changing


@dataclass(frozen=True)
class Change:
    path: str
    added: int | None
    deleted: int | None


def read_changes(base: str, cwd: Path) -> list[Change]:
    """Diff the merge-base against tracked working state, including staged edits."""
    merge_base = subprocess.run(  # noqa: S603 -- argv, no shell or ref options
        ["git", "merge-base", "--", base, "HEAD"],
        cwd=cwd,
        capture_output=True,
        check=True,
        text=True,
    ).stdout.strip()
    result = subprocess.run(  # noqa: S603 -- argv, revision separated from paths
        ["git", "diff", "--no-renames", "--numstat", "-z", merge_base, "--"],
        cwd=cwd,
        capture_output=True,
        check=True,
    )
    changes = []
    for record in result.stdout.split(b"\0"):
        if not record:
            continue
        added, deleted, raw_path = record.split(b"\t", 2)
        changes.append(
            Change(
                raw_path.decode("utf-8", errors="surrogateescape"),
                None if added == b"-" else int(added),
                None if deleted == b"-" else int(deleted),
            )
        )
    return changes


def path_risk(change: Change) -> tuple[int, str]:
    """0=low, 1=medium, 2=high. Semantic escalation remains a reviewer duty."""
    path = PurePosixPath(change.path)
    if _is_governor_changing([change.path]):
        return 2, "governor trigger"
    if change.added is None or change.deleted is None:
        return 2, "binary diff: line size unknown"
    parts = {part.lower() for part in path.parts}
    sensitive = {
        "auth",
        "authentication",
        "authorization",
        "security",
        "secrets",
        "credentials",
    }
    stem = path.stem.lower()
    if (
        change.path.startswith(("migrations/", ".github/workflows/"))
        or parts & sensitive
        or any(term in stem for term in ("auth", "security", "credential", "secret"))
        or stem.startswith(".env")
        or "schemas" in parts
        or "payloads" in parts
        or "models" in parts
    ):
        return 2, "security, schema, migration, or CI path"
    if change.path.startswith(
        ("src/", "examples/", "tools/", "_env/")
    ) or path.name in {
        "pyproject.toml",
        "uv.lock",
        "Makefile",
        "Dockerfile",
        "docker-compose.yml",
    }:
        return 1, "runtime, build, or tooling path"
    if change.path.startswith(("docs/", "tests/")) or path.suffix.lower() in {
        ".md",
        ".rst",
        ".txt",
        ".svg",
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
    }:
        return 0, "general documentation, asset, or test"
    return 1, "unclassified path: inspect manually"


def packet(changes: list[Change]) -> dict:
    total = sum((item.added or 0) + (item.deleted or 0) for item in changes)
    ranked = [(path_risk(item), item) for item in changes]
    risk = max([score for (score, _), _ in ranked], default=0)
    reasons = sorted({reason for (score, reason), _ in ranked if score == risk})
    if total > 400:
        risk = max(risk, 1)
        reasons.append("more than 400 added+deleted lines")
    ranked.sort(key=lambda row: (-row[0][0], row[1].path))
    return {
        "risk": ("low", "medium", "high")[risk],
        "reasons": reasons,
        "added_deleted_lines": total,
        "size_complete": all(item.added is not None for item in changes),
        "files": [
            {**asdict(item), "risk": ("low", "medium", "high")[score], "reason": reason}
            for (score, reason), item in ranked
        ],
        "verification": "not run by this command",
        "scope": "tracked working diff against merge-base(base, HEAD); stage new files before running",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base", default="origin/main", help="base revision (default: origin/main)"
    )
    args = parser.parse_args()
    if args.base.startswith("-"):
        parser.error("base must be a revision, not an option")
    print(json.dumps(packet(read_changes(args.base, Path.cwd())), indent=2))


if __name__ == "__main__":
    main()
