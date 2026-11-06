"""Block factual context growth over tracked harness budgets (#416).

Read working-tree contents selected by the git index, like check_doc_links.py.
Fenced examples are excluded from line checks, never from file byte totals.
Shared prose/table line caps are intentionally deferred; only rules' sync
headers, project-dna's sync header, and the recent-status table are line-gated.
See ADR 059 for the ratchet and content-date policy.
"""

from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

AUTOLOAD_MAX = 40960
RULE_FILE_MAX = 16384
SYNC_LINE_MAX = 200
RECENT_ROW_MAX = 300
AGENTS_MAX = 30720
REPO_ROOT = Path(__file__).resolve().parent.parent
# Any indentation opens a fence: list-nested fences (four or more spaces) are
# common here. Known limit: backticks inside a top-level indented code block
# also open one; telling the two apart needs container-aware Markdown parsing.
FENCE = re.compile(r"^\s*(`{3,}|~{3,})")


@dataclass(frozen=True)
class Violation:
    path: str
    line: int
    kind: str
    actual: int
    allowed: int
    destination: str

    def __str__(self) -> str:
        return (
            f"{self.path}:{self.line}: context-budget {self.kind}: "
            f"{self.actual} bytes (allowed {self.allowed}); {self.destination}"
        )


def tracked_paths(root: Path) -> list[str]:
    """Use the full index, including new staged files but never untracked files."""
    result = subprocess.run(
        ["git", "ls-files", "-z"], cwd=root, check=True, capture_output=True
    )
    return result.stdout.decode("utf-8").rstrip("\0").split("\0")


def has_paths_frontmatter(source: str) -> bool:
    """Recognize a nonempty paths key only inside leading YAML frontmatter."""
    lines = source.splitlines()
    if not lines or lines[0].strip() != "---":
        return False
    if "---" not in [line.strip() for line in lines[1:]]:
        return False
    for index, line in enumerate(lines[1:], 1):
        if line.strip() == "---":
            break
        match = re.match(r"^paths:\s*(.*?)\s*(?:#.*)?$", line)
        if not match:
            continue
        value = match.group(1).strip()
        if (
            value.lower() == "null"
            or re.sub(r"\s", "", value) == "[]"
            or value in {"~", "''", '""'}
        ):
            return False
        if value.startswith("[") and value.endswith("]"):
            return any(
                item.strip().strip("\"'").strip() for item in value[1:-1].split(",")
            )
        if value:
            return True
        for following in lines[index + 1 :]:
            if not following.strip() or following.lstrip().startswith("#"):
                continue
            item = following.lstrip()
            if item != "-" and not item.startswith("- "):
                return False
            if item[1:].split("#", 1)[0].strip().strip("\"'").strip():
                return True
        return False
    return False


def visible_lines(source: str):
    """Yield non-fenced lines without changing their original line numbers."""
    fence_char = ""
    fence_length = 0
    fence_start = 0
    for number, line in enumerate(source.splitlines(), 1):
        match = FENCE.match(line)
        if match:
            marker = match.group(1)
            if not fence_char:
                fence_char, fence_length = marker[0], len(marker)
                fence_start = number
            elif marker[0] == fence_char and len(marker) >= fence_length:
                if not line[match.end() :].strip():
                    fence_char = ""
            continue
        if not fence_char:
            yield number, line
    if fence_char:
        raise ValueError(fence_start)


def check_budget(root: Path, paths) -> tuple[list[Violation], int]:
    failures: list[Violation] = []
    total = 0
    for path in sorted(set(paths)):
        rule = path.startswith(".claude/rules/") and path.endswith(".md")
        dna = path == "docs/ai/shared/project-dna.md"
        if not (rule or dna or path in {"AGENTS.md", "CLAUDE.md"}):
            continue
        try:
            data = (root / path).read_bytes()
            source = data.decode("utf-8")
        except (OSError, UnicodeError):
            failures.append(
                Violation(path, 1, "read", 0, 0, "restore the tracked UTF-8 file")
            )
            continue
        size = len(data)
        cap = AGENTS_MAX if path == "AGENTS.md" else RULE_FILE_MAX if rule else None
        if cap is not None and size > cap:
            failures.append(
                Violation(
                    path,
                    1,
                    "file",
                    size,
                    cap,
                    "move current detail to docs/ai/shared/; archive historical text only in a deliberate governor-changing migration",
                )
            )
        if path == "CLAUDE.md" or (rule and not has_paths_frontmatter(source)):
            total += size
        recent = False
        sync_headers = 0
        try:
            lines = list(visible_lines(source))
        except ValueError as exc:
            failures.append(
                Violation(
                    path,
                    int(exc.args[0]),
                    "unclosed fence",
                    size,
                    0,
                    "close the Markdown fence so line checks remain visible",
                )
            )
            continue
        for number, line in lines:
            size = len(line.encode("utf-8"))
            if (rule or dna) and line.startswith(("> Last synced:", "> Last updated:")):
                sync_headers += 1
                if sync_headers > 1:
                    failures.append(
                        Violation(
                            path,
                            number,
                            "duplicate sync header",
                            size,
                            0,
                            "keep one sync header per file; routine history belongs in git/CHANGELOG",
                        )
                    )
            if (
                (rule or dna)
                and line.startswith(("> Last synced:", "> Last updated:"))
                and size > SYNC_LINE_MAX
            ):
                failures.append(
                    Violation(
                        path,
                        number,
                        "sync header",
                        size,
                        SYNC_LINE_MAX,
                        "trim; use git/CHANGELOG for routine history; docs/history/archive/project-status/ only in a deliberate governor-changing migration",
                    )
                )
            elif (rule or dna) and line.startswith(
                ("> Last synced:", "> Last updated:")
            ):
                if (
                    not re.fullmatch(
                        r"> Last (?:synced|updated): \d{4}-\d{2}-\d{2} via .{0,80}",
                        line,
                    )
                    or "Prior:" in line
                ):
                    failures.append(
                        Violation(
                            path,
                            number,
                            "header format",
                            size,
                            SYNC_LINE_MAX,
                            "use a single date via reference; keep narrative in git/CHANGELOG",
                        )
                    )
            if (rule or dna) and line.lstrip().startswith("> Prior:"):
                failures.append(
                    Violation(
                        path,
                        number,
                        "retrospective header",
                        size,
                        0,
                        "remove Prior chains; preserve provenance in git/CHANGELOG",
                    )
                )
            if path == ".claude/rules/project-status.md":
                if line.startswith("## "):
                    recent = line.startswith("## Recent Major Changes")
                if recent and line.lstrip().startswith("|") and size > RECENT_ROW_MAX:
                    failures.append(
                        Violation(
                            path,
                            number,
                            "recent row",
                            size,
                            RECENT_ROW_MAX,
                            "keep one sentence; move narrative to CHANGELOG and the PR body",
                        )
                    )
    if total > AUTOLOAD_MAX:
        failures.append(
            Violation(
                "CLAUDE.md",
                1,
                "total auto-loaded",
                total,
                AUTOLOAD_MAX,
                "move narrative to docs/ai/shared/ or CHANGELOG",
            )
        )
    return failures, total


def main() -> int:
    try:
        failures, total = check_budget(REPO_ROOT, tracked_paths(REPO_ROOT))
    except (OSError, subprocess.CalledProcessError) as exc:
        print(f"context-budget: cannot read git index: {exc}", file=sys.stderr)
        return 1
    for failure in failures:
        print(failure)
    print(
        f"Context budget: {total}/{AUTOLOAD_MAX} auto-loaded bytes; {len(failures)} violation(s)"
    )
    return int(bool(failures))


if __name__ == "__main__":
    sys.exit(main())
