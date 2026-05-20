"""Tier 1 Language Policy checker.

Enforces AGENTS.md § Language Policy: shared-repo Tier 1 paths must not
contain Korean (Hangul) prose. Bilingual escape tokens and locale data
files (LOCALE_DATA_FILES) are the two narrowly-scoped exceptions, and they
are scoped per-file so a token literal cannot launder Korean prose
elsewhere.

Scope today is **Korean prose only**. Other-language detection (Chinese,
Japanese, encoded payloads via base64 / HTML entities) is intentionally out
of scope; if a leak appears in another form, expand the detector first and
update AGENTS.md § Language Policy to match the new scope.

Used by:
- `.pre-commit-config.yaml` `tier1-language-policy` hook (filenames passed by argv)
- `tests/unit/agents_shared/test_language_policy.py` (imported as a library)
- Ad-hoc dry-run: `python3 tools/check_language_policy.py` (no argv = full repo scan)

The checker is the single source of truth for the policy. Do not duplicate
its logic in shell pipelines or yaml regexes. The pre-commit `files:` regex
deliberately mirrors `TIER1_GLOBS`; a drift test asserts they stay aligned.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

# ---------------------------------------------------------------------------
# Repo paths
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Hangul detection
# ---------------------------------------------------------------------------
# Three Unicode blocks cover Korean prose:
#   U+AC00-U+D7A3 : precomposed Hangul syllables (the common case)
#   U+1100-U+11FF : Hangul Jamo (decomposed form)
#   U+3130-U+318F : Hangul Compatibility Jamo (legacy CJK input)
#
# The checker's enforcement scope is Korean only — see module docstring for
# why other CJK languages and encoded payloads are intentionally out of scope.
HANGUL_RE = re.compile(r"[가-힣ᄀ-ᇿ㄰-㆏]")

# ---------------------------------------------------------------------------
# Tier 1 path globs
# Mirrors AGENTS.md § Language Policy. The drift test in
# `test_language_policy.py` asserts these stay in sync with the policy section.
# ---------------------------------------------------------------------------
TIER1_GLOBS: tuple[str, ...] = (
    "AGENTS.md",
    "CLAUDE.md",
    "CONTRIBUTING.md",
    "CODE_OF_CONDUCT.md",
    "SECURITY.md",
    "docs/ai/shared/**/*.md",
    "docs/history/**/*.md",
    ".claude/rules/**/*.md",
    ".claude/hooks/**/*",
    ".claude/skills/**/*.md",
    ".codex/rules/**/*",
    ".codex/hooks/**/*",
    ".agents/**/*.py",
    ".agents/**/*.md",
    ".agents/**/*.sh",
    ".github/pull_request_template.md",
    ".github/workflows/**/*.yml",
    ".github/workflows/**/*.yaml",
)

# ---------------------------------------------------------------------------
# Per-file token literal allowlist
# ---------------------------------------------------------------------------
# Korean token-vocabulary references are allowed ONLY in the files that
# legitimately need them (the policy table, the parser source, docstring
# references). A global allowlist would let `[자명] 한국어 prose` pass; per-file
# scoping forces token mentions to live where they belong.
#
# Keys are repo-root-relative POSIX paths. Values are sets of literal Korean
# substrings the checker may strip from a line before re-checking for Hangul.
TOKEN_LITERALS_BY_FILE: dict[str, set[str]] = {
    # Canonical token vocabulary table + Default Coding Flow references.
    "AGENTS.md": {"[자명]", "[긴급]", "[탐색]", "자명", "긴급", "탐색"},
    "CLAUDE.md": {"[자명]", "[긴급]", "[탐색]"},
    # Parser source: the regex literally lists the Korean token strings.
    ".agents/shared/governor/tokens.py": {"자명", "긴급", "탐색", "[탐색]"},
    # Token references in shared-module reminder strings and docstrings.
    ".agents/shared/governor/verify.py": {"[탐색]", "탐색"},
    ".agents/shared/governor/completion_gate.py": {"[탐색]", "탐색"},
    # Codex hook docstring references the token.
    ".codex/hooks/verify_first.py": {"[탐색]", "탐색"},
    # Claude status and shared drift docs summarise token-vocabulary decisions.
    ".claude/rules/project-status.md": {
        "[자명]",
        "[긴급]",
        "[탐색]",
        "자명",
        "긴급",
        "탐색",
    },
    "docs/ai/shared/drift-checklist.md": {
        "[자명]",
        "[긴급]",
        "[탐색]",
        "자명",
        "긴급",
        "탐색",
    },
    # Migration strategy + target operating model + repo facts mention tokens
    # in policy-table form. Reference docs that quote AGENTS.md verbatim.
    "docs/ai/shared/migration-strategy.md": {
        "[자명]",
        "[긴급]",
        "[탐색]",
        "자명",
        "긴급",
        "탐색",
    },
    "docs/ai/shared/target-operating-model.md": {
        "[자명]",
        "[긴급]",
        "[탐색]",
        "자명",
        "긴급",
        "탐색",
    },
    "docs/ai/shared/repo-facts.md": {
        "[자명]",
        "[긴급]",
        "[탐색]",
        "자명",
        "긴급",
        "탐색",
    },
    # ADR 045 introduces the token vocabulary.
    "docs/history/045-hybrid-harness-target-architecture.md": {
        "[자명]",
        "[긴급]",
        "[탐색]",
        "자명",
        "긴급",
        "탐색",
    },
    # Skills that reference exception tokens.
    "docs/ai/shared/skills/fix-bug.md": {"[자명]", "[긴급]", "[탐색]", "긴급"},
    "docs/ai/shared/skills/onboard.md": {"[자명]", "[긴급]", "[탐색]", "탐색"},
    ".claude/skills/fix-bug/SKILL.md": {"[자명]", "[긴급]", "[탐색]", "긴급"},
    ".claude/skills/onboard/SKILL.md": {"[자명]", "[긴급]", "[탐색]", "탐색"},
    ".agents/skills/fix-bug/SKILL.md": {"[자명]", "[긴급]", "[탐색]", "긴급"},
    ".agents/skills/onboard/SKILL.md": {"[자명]", "[긴급]", "[탐색]", "탐색"},
    # Review-log entries that preserve token-vocabulary decisions.
    # ADR 047 (PR #159) closes the governor-review-log/ archive — these five
    # frozen entries retain their existing token allowlist (option F1) so the
    # historical archive continues to pass the language policy check. Do NOT
    # extend this block: new governor-changing PRs use the PR-description
    # Governor Footer block instead of writing new log entries, so no new
    # files should ever require entries here. Archive moved to
    # docs/history/archive/governor-review-log/ per ADR 047 post-decision note
    # (#160).
    "docs/history/archive/governor-review-log/pr-125-hybrid-harness-target-architecture.md": {
        "[자명]",
        "[긴급]",
        "[탐색]",
        "자명",
        "긴급",
        "탐색",
    },
    "docs/history/archive/governor-review-log/pr-126-userpromptsubmit-token-parser.md": {
        "[자명]",
        "[긴급]",
        "[탐색]",
        "자명",
        "긴급",
        "탐색",
    },
    "docs/history/archive/governor-review-log/pr-127-verify-first-adapters.md": {
        "[탐색]",
        "탐색",
    },
    "docs/history/archive/governor-review-log/pr-128-completion-gate-stop-adapter.md": {
        "[탐색]",
        "탐색",
    },
    "docs/history/archive/governor-review-log/pr-132-language-policy.md": {
        "[자명]",
        "[긴급]",
        "[탐색]",
        "자명",
        "긴급",
        "탐색",
    },
}

# ---------------------------------------------------------------------------
# Locale data files — file-wide skip (issue #133, AGENT_LOCALE)
# ---------------------------------------------------------------------------
# Files listed here are the canonical runtime source for translated terminal
# output. Korean (and future other-language) translation strings are
# permitted by design. ``find_violations()`` returns ``[]`` for any path in
# this set without scanning content. Adding a new locale data file requires:
#   1. Add the path here.
#   2. Add a bullet to AGENTS.md § Language Policy → Exemptions.
#   3. Update the expected key set in tests/unit/agents_shared/test_locale.py.
#   4. Add an AST/tokenize guard for Hangul placement inside the new file.
LOCALE_DATA_FILES: frozenset[str] = frozenset({".agents/shared/governor/locale.py"})


# ---------------------------------------------------------------------------
# Provenance prefixes — only valid in governor-review-log/*.md
# ---------------------------------------------------------------------------
# Korean text is allowed on a single line if and only if that line starts
# with one of these blockquote prefixes. Multi-line preserved Korean must
# repeat the prefix on every line.
PROVENANCE_PREFIXES: tuple[str, ...] = (
    "> Original user/owner statement (ko, verbatim):",
    "> Original reviewer verdict (ko, verbatim):",
    "> Historical Korean excerpt (ko, verbatim):",
)

REVIEW_LOG_GLOB = "docs/history/archive/governor-review-log/"

# ---------------------------------------------------------------------------
# README link-label exemption
# ---------------------------------------------------------------------------
# README.md L31 has a `<a href="docs/README.ko.md">한국어</a>` link label
# pointing to a deliberately translated sibling document. README.md is not in
# TIER1_GLOBS, so the checker never sees it — listed here for reference only.

# ---------------------------------------------------------------------------
# Markdown code-block exemption
# ---------------------------------------------------------------------------
# Korean inside fenced ``` blocks in .md files is permitted (literal code or
# quoted samples, not prose). Inline backticks are still line-visible prose and
# are scanned; allowed bilingual tokens must be covered by the per-file
# allowlist. Outside .md files (e.g. .py source), Korean string literals are
# violations regardless.

MARKDOWN_EXTENSIONS = {".md"}

# CommonMark allows up to 3 spaces of leading indentation before a fence.
# Fences inside list items (commonly indented 2 or 4 spaces in this repo)
# are intentionally not covered — pre-commit/CI will surface those as
# violations and prompt the author to outdent the code block.
FENCED_CODE_RE = re.compile(r"^[ ]{0,3}```", re.MULTILINE)


# ---------------------------------------------------------------------------
# Violation record
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Violation:
    path: str
    line_number: int
    line_content: str
    reason: str

    def format(self) -> str:
        return f"{self.path}:{self.line_number}: {self.reason}\n  {self.line_content!r}"


# ---------------------------------------------------------------------------
# Per-line check
# ---------------------------------------------------------------------------


def _mask_token_literals(line: str, allowed: set[str]) -> str:
    """Remove token-literal occurrences from a line so remaining Hangul fails."""
    masked = line
    # Sort longest-first so `[자명]` masks before `자명` would.
    for literal in sorted(allowed, key=len, reverse=True):
        masked = masked.replace(literal, "")
    return masked


def _is_provenance_line(rel_path: str, line: str) -> bool:
    if not rel_path.startswith(REVIEW_LOG_GLOB):
        return False
    stripped = line.lstrip()
    return any(stripped.startswith(prefix) for prefix in PROVENANCE_PREFIXES)


def _strip_fenced_blocks(text: str) -> str:
    """Replace fenced code blocks with blank lines (preserves line numbers).

    Tolerates up to 3 spaces of leading indentation per CommonMark §4.5.
    """
    out_lines: list[str] = []
    in_fence = False
    for raw in text.splitlines():
        if FENCED_CODE_RE.match(raw):
            in_fence = not in_fence
            out_lines.append("")
            continue
        out_lines.append("" if in_fence else raw)
    return "\n".join(out_lines)


def _next_non_blank_line(lines: list[str], idx: int) -> tuple[int, str] | None:
    """Return (1-based line number, content) for the next non-blank line
    after `lines[idx]` (idx is 0-based). None if EOF."""
    j = idx + 1
    while j < len(lines):
        if lines[j].strip():
            return (j + 1, lines[j])
        j += 1
    return None


def find_violations(path: Path, *, repo_root: Path = REPO_ROOT) -> list[Violation]:
    """Return all Tier 1 violations in `path`. Empty list = clean."""
    try:
        rel = path.resolve().relative_to(repo_root)
    except ValueError:
        rel = path
    rel_str = rel.as_posix()

    # Locale data files are exempt: their entire purpose is to carry
    # translated strings. Hangul placement inside the file is enforced by
    # tests/unit/agents_shared/test_locale.py (AST + tokenize guard).
    if rel_str in LOCALE_DATA_FILES:
        return []

    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []

    is_markdown = path.suffix in MARKDOWN_EXTENSIONS
    if is_markdown:
        text = _strip_fenced_blocks(text)

    allowed_tokens = TOKEN_LITERALS_BY_FILE.get(rel_str, set())
    raw_lines = text.splitlines()

    violations: list[Violation] = []
    reported_lines: set[int] = set()
    for idx, line in enumerate(raw_lines, start=1):
        check_line = line

        if not HANGUL_RE.search(check_line):
            continue

        if _is_provenance_line(rel_str, check_line):
            # Provenance prefix is allowed, but the policy says an
            # English normalised line must follow on the next non-blank
            # line. Verify it (R132-IMPL.3).
            next_line = _next_non_blank_line(raw_lines, idx - 1)
            if next_line is None or HANGUL_RE.search(next_line[1]):
                target_line = next_line[0] if next_line is not None else idx
                target_content = next_line[1] if next_line is not None else ""
                if target_line not in reported_lines:
                    violations.append(
                        Violation(
                            path=rel_str,
                            line_number=target_line,
                            line_content=target_content.rstrip(),
                            reason=(
                                "missing English normalised line after provenance "
                                "prefix on the previous line (AGENTS.md § Language "
                                "Policy → Exemptions: docs/history/archive/"
                                "governor-review-log/**)"
                            ),
                        )
                    )
                    reported_lines.add(target_line)
            continue

        if allowed_tokens:
            check_line = _mask_token_literals(check_line, allowed_tokens)
            if not HANGUL_RE.search(check_line):
                continue

        if idx in reported_lines:
            continue
        violations.append(
            Violation(
                path=rel_str,
                line_number=idx,
                line_content=line.rstrip(),
                reason="non-allowlisted Hangul in Tier 1 path",
            )
        )
        reported_lines.add(idx)
    return violations


# ---------------------------------------------------------------------------
# Path discovery
# ---------------------------------------------------------------------------


def discover_tier1_paths(repo_root: Path = REPO_ROOT) -> list[Path]:
    seen: set[Path] = set()
    for pattern in TIER1_GLOBS:
        for match in repo_root.glob(pattern):
            if match.is_file():
                seen.add(match.resolve())
    return sorted(seen)


def resolve_argv_paths(
    argv_paths: list[str], repo_root: Path = REPO_ROOT
) -> list[Path]:
    out: list[Path] = []
    for raw in argv_paths:
        p = Path(raw)
        if not p.is_absolute():
            p = (repo_root / p).resolve()
        if p.is_file():
            out.append(p)
    return out


def filter_to_tier1(paths: list[Path], repo_root: Path = REPO_ROOT) -> list[Path]:
    """Keep only paths matching TIER1_GLOBS. Used in pre-commit mode where the
    `files:` glob already filters, but we double-check defensively."""
    discovered = set(discover_tier1_paths(repo_root))
    return [p for p in paths if p in discovered]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def run(argv_paths: list[str], *, repo_root: Path = REPO_ROOT) -> int:
    if argv_paths:
        candidates = filter_to_tier1(
            resolve_argv_paths(argv_paths, repo_root), repo_root
        )
    else:
        candidates = discover_tier1_paths(repo_root)

    all_violations: list[Violation] = []
    for path in candidates:
        all_violations.extend(find_violations(path, repo_root=repo_root))

    if all_violations:
        print(
            f"Tier 1 Language Policy violations found "
            f"({len(all_violations)} across {len({v.path for v in all_violations})} files):",
            file=sys.stderr,
        )
        for v in all_violations:
            print(v.format(), file=sys.stderr)
        print(
            "\nSee AGENTS.md § Language Policy for the rule. "
            "Bilingual escape tokens [자명]/[긴급]/[탐색] and locale data files "
            "(LOCALE_DATA_FILES) are the two narrowly-scoped exceptions.",
            file=sys.stderr,
        )
        return 1

    print(
        f"Tier 1 Language Policy: 0 violations across {len(candidates)} scanned files."
    )
    return 0


def main() -> int:
    return run(sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
