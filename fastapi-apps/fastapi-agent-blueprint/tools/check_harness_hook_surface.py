#!/usr/bin/env python3
"""Check agent hook execution surfaces for bare ``python3`` calls.

Scope is intentionally narrow:
* .codex/hooks.json command strings
* .gemini/settings.json command strings
* .claude/hooks/*.sh executable lines

Docs, Python hook docstrings, shebangs, and pre-commit examples are outside
this check. Those surfaces may mention Python commands without being live
agent hook execution paths.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

BARE_PYTHON3_RE = re.compile(r"(?<![\w./-])python3(?![\w.-])")


@dataclass(frozen=True)
class Violation:
    path: Path
    line: int
    text: str

    def render(self, root: Path) -> str:
        rel = self.path.relative_to(root)
        return f"{rel}:{self.line}: bare python3 in hook execution surface: {self.text}"


def _codex_commands(path: Path) -> Iterable[tuple[str, str]]:
    yield from _json_hook_commands(path)


def _gemini_commands(path: Path) -> Iterable[tuple[str, str]]:
    yield from _json_hook_commands(path)


def _json_hook_commands(path: Path) -> Iterable[tuple[str, str]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    hooks = data.get("hooks", {})
    if not isinstance(hooks, dict):
        return
    for event_name, event_blocks in hooks.items():
        if not isinstance(event_blocks, list):
            continue
        for block_index, block in enumerate(event_blocks):
            if not isinstance(block, dict):
                continue
            for hook_index, hook in enumerate(block.get("hooks", [])):
                if not isinstance(hook, dict):
                    continue
                command = hook.get("command", "")
                if isinstance(command, str):
                    label = f"{event_name}[{block_index}].hooks[{hook_index}]"
                    yield label, command


def _strip_shell_comment(line: str) -> str:
    """Best-effort shell comment stripping for simple hook wrapper lines."""

    in_single = False
    in_double = False
    escaped = False
    for idx, char in enumerate(line):
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char == "'" and not in_double:
            in_single = not in_single
            continue
        if char == '"' and not in_single:
            in_double = not in_double
            continue
        if char == "#" and not in_single and not in_double:
            return line[:idx]
    return line


def check_root(root: Path) -> list[Violation]:
    violations: list[Violation] = []

    codex_hooks = root / ".codex" / "hooks.json"
    if codex_hooks.exists():
        try:
            for label, command in _codex_commands(codex_hooks):
                if BARE_PYTHON3_RE.search(command):
                    violations.append(Violation(codex_hooks, 1, f"{label}: {command}"))
        except json.JSONDecodeError as exc:
            violations.append(
                Violation(codex_hooks, exc.lineno, f"invalid JSON: {exc}")
            )

    gemini_settings = root / ".gemini" / "settings.json"
    if gemini_settings.exists():
        try:
            for label, command in _gemini_commands(gemini_settings):
                if BARE_PYTHON3_RE.search(command):
                    violations.append(
                        Violation(gemini_settings, 1, f"{label}: {command}")
                    )
        except json.JSONDecodeError as exc:
            violations.append(
                Violation(gemini_settings, exc.lineno, f"invalid JSON: {exc}")
            )

    claude_hook_dir = root / ".claude" / "hooks"
    for shell_hook in sorted(claude_hook_dir.glob("*.sh")):
        for line_no, line in enumerate(
            shell_hook.read_text(encoding="utf-8").splitlines(), 1
        ):
            executable = _strip_shell_comment(line).strip()
            if executable and BARE_PYTHON3_RE.search(executable):
                violations.append(Violation(shell_hook, line_no, executable))

    return violations


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parents[1]
    )
    args = parser.parse_args(argv)

    root = args.root.resolve()
    violations = check_root(root)
    if violations:
        for violation in violations:
            print(violation.render(root), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
