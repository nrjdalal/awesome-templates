"""Tier 1 Language Policy regression tests (PR #131).

These tests reuse the shared checker at ``tools/check_language_policy.py``
so the pre-commit hook and the test suite enforce the same allowlist.
Adding a case here that the hook cannot also enforce indicates a checker
gap, not a test gap — fix the checker.

Coverage:

1. Korean prose in a Tier 1 path is flagged.
2. Bilingual escape tokens in their per-file allowlist are accepted.
3. Provenance-prefixed Korean in a governor-review-log entry is accepted.
4. Korean in a review-log entry without the provenance prefix is flagged.
5. README.md L31 ``한국어`` link label is exempt (README is not in
   TIER1_GLOBS).
6. Multi-line preserved Korean must repeat the prefix on every line —
   the second line without a prefix is a violation.
7. Korean inside a fenced code block in a ``.md`` file is exempt.
8. Korean in a ``.py`` source file string literal is a violation
   (no code-block exemption outside ``.md``).
9. Drift test: every Tier 1 path bullet in
   ``AGENTS.md § Language Policy`` resolves to a path covered by the
   checker's ``TIER1_GLOBS``, and every glob has a corresponding policy
   bullet. Prevents silent drift between the policy text and the
   enforcer.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]


def _import_checker():
    """Import tools.check_language_policy without adding it to package layout."""
    import importlib.util
    import sys

    module_name = "_check_language_policy"
    if module_name in sys.modules:
        return sys.modules[module_name]
    module_path = REPO_ROOT / "tools" / "check_language_policy.py"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module  # required for @dataclass(frozen=True)
    spec.loader.exec_module(module)
    return module


CHECKER = _import_checker()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _scan(tmp_path: Path, rel_path: str, content: str):
    target = tmp_path / rel_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return CHECKER.find_violations(target, repo_root=tmp_path)


# ---------------------------------------------------------------------------
# 1-2. Token-vocabulary allowlist — positive and negative cases
# ---------------------------------------------------------------------------


def test_korean_prose_in_claude_rules_is_violation(tmp_path: Path) -> None:
    violations = _scan(
        tmp_path,
        ".claude/rules/commands.md",
        "# 개발환경 셋업\nmake setup\n",
    )
    assert len(violations) == 1
    assert violations[0].line_number == 1


def test_bilingual_token_in_agents_md_passes(tmp_path: Path) -> None:
    violations = _scan(
        tmp_path,
        "AGENTS.md",
        "| `[trivial]` | `[자명]` | Self-evident change |\n",
    )
    assert violations == []


def test_token_literal_does_not_launder_korean_prose(tmp_path: Path) -> None:
    """Per-file allowlist must reject Korean prose appearing on the same
    line as a token literal — the token is masked, then any remaining
    Hangul fails."""
    violations = _scan(
        tmp_path,
        "AGENTS.md",
        "| `[trivial]` | `[자명]` | 한국어 prose |\n",
    )
    assert len(violations) == 1


# ---------------------------------------------------------------------------
# 3-6. governor-review-log provenance prefix rules
# ---------------------------------------------------------------------------


def test_review_log_provenance_prefix_passes(tmp_path: Path) -> None:
    violations = _scan(
        tmp_path,
        "docs/history/archive/governor-review-log/pr-999-example.md",
        "> Original reviewer verdict (ko, verbatim): 보완 필요\n"
        "> English normalised verdict: needs follow-up.\n",
    )
    assert violations == []


def test_review_log_korean_without_prefix_is_violation(tmp_path: Path) -> None:
    violations = _scan(
        tmp_path,
        "docs/history/archive/governor-review-log/pr-999-example.md",
        "Some random text 보완 필요\n",
    )
    assert len(violations) == 1


def test_review_log_multiline_provenance_must_repeat_prefix(
    tmp_path: Path,
) -> None:
    """Multi-line preserved Korean must repeat the provenance prefix on
    every line. A continuation line without the prefix is a violation."""
    violations = _scan(
        tmp_path,
        "docs/history/archive/governor-review-log/pr-999-example.md",
        "> Original user/owner statement (ko, verbatim): 첫 번째 줄\n"
        "두 번째 줄에는 prefix가 없음\n",
    )
    # The first line is allowed (prefixed). The second is not.
    # R132-IMPL.3 also flags the missing English summary after the prefixed
    # line, but the second-line Hangul violation lands on the same line.
    assert len(violations) == 1
    assert violations[0].line_number == 2


def test_review_log_provenance_without_english_summary_is_violation(
    tmp_path: Path,
) -> None:
    """R132-IMPL.3: AGENTS.md § Language Policy says an English normalised
    line must follow each provenance prefix on the next non-blank line.
    A provenance-only entry with no English summary is a violation."""
    violations = _scan(
        tmp_path,
        "docs/history/archive/governor-review-log/pr-999-example.md",
        "> Original reviewer verdict (ko, verbatim): 보완 필요\n",
    )
    assert len(violations) == 1
    assert "English normalised line" in violations[0].reason


def test_review_log_provenance_with_blank_then_english_passes(
    tmp_path: Path,
) -> None:
    """A blank line between the provenance prefix and the English summary
    is acceptable — the next *non-blank* line is what the checker examines."""
    violations = _scan(
        tmp_path,
        "docs/history/archive/governor-review-log/pr-999-example.md",
        "> Original reviewer verdict (ko, verbatim): 보완 필요\n\nneeds follow-up.\n",
    )
    assert violations == []


def test_review_log_consecutive_provenance_lines_each_summarised(
    tmp_path: Path,
) -> None:
    """Multi-line preserved Korean repeats the prefix on every line; each
    such line gets its own English summary on the line after it. The
    checker should not double-count the chain."""
    content = (
        "> Original user/owner statement (ko, verbatim): 첫 번째 한국어 줄\n"
        "First English line.\n"
        "> Original user/owner statement (ko, verbatim): 두 번째 한국어 줄\n"
        "Second English line.\n"
    )
    violations = _scan(
        tmp_path,
        "docs/history/archive/governor-review-log/pr-999-example.md",
        content,
    )
    assert violations == []


def test_review_log_adjacent_provenance_lines_still_need_english_summary(
    tmp_path: Path,
) -> None:
    """A second provenance line is not an English summary for the first one."""
    violations = _scan(
        tmp_path,
        "docs/history/archive/governor-review-log/pr-999-example.md",
        "> Original user/owner statement (ko, verbatim): 첫 번째 한국어 줄\n"
        "> Original user/owner statement (ko, verbatim): 두 번째 한국어 줄\n"
        "Second English line.\n",
    )
    assert len(violations) == 1
    assert violations[0].line_number == 2
    assert "English normalised line" in violations[0].reason


# ---------------------------------------------------------------------------
# 5. README.md exemption — pointed out as a Tier-1-exclusion path
# ---------------------------------------------------------------------------


def test_readme_md_is_not_in_tier1_globs() -> None:
    """README.md is intentionally exempt — its `한국어` link label points
    at the deliberately translated `docs/README.ko.md`. Verified by
    confirming README.md is absent from the discovered Tier 1 set."""
    discovered = CHECKER.discover_tier1_paths(REPO_ROOT)
    rels = {p.relative_to(REPO_ROOT).as_posix() for p in discovered}
    assert "README.md" not in rels


# ---------------------------------------------------------------------------
# 7-8. Markdown-only code-block exemption
# ---------------------------------------------------------------------------


def test_markdown_fenced_code_block_korean_is_exempt(tmp_path: Path) -> None:
    """Korean inside a fenced ``` block in a .md file is treated as
    literal code/sample, not prose — exempt by policy."""
    violations = _scan(
        tmp_path,
        "docs/ai/shared/example.md",
        'Some prose.\n\n```\nprint("한국어")\n```\n\nMore prose.\n',
    )
    assert violations == []


def test_markdown_indented_fenced_block_is_exempt(tmp_path: Path) -> None:
    """CommonMark allows up to 3 spaces of leading indentation before a
    fence (R132-IMPL.5). The checker tolerates the same so list-adjacent
    code blocks containing Korean samples do not false-positive."""
    violations = _scan(
        tmp_path,
        "docs/ai/shared/example.md",
        'Intro prose.\n\n   ```\n   print("한국어 샘플")\n   ```\n\nOutro prose.\n',
    )
    assert violations == []


def test_markdown_inline_code_korean_is_violation(tmp_path: Path) -> None:
    """Inline backticks are line-visible prose, not a fenced-code exemption."""
    violations = _scan(
        tmp_path,
        "docs/ai/shared/example.md",
        "Do not hide Korean rationale in `한국어 메모` inline code.\n",
    )
    assert len(violations) == 1


def test_markdown_html_comment_korean_is_violation(tmp_path: Path) -> None:
    """HTML comments are hidden in rendered Markdown but visible in source."""
    violations = _scan(
        tmp_path,
        "docs/ai/shared/example.md",
        "<!-- 한국어 rationale -->\n",
    )
    assert len(violations) == 1


def test_python_source_korean_string_literal_is_violation(
    tmp_path: Path,
) -> None:
    """No code-block exemption applies outside .md files. A Korean
    string literal in a .py source counts as policy violation."""
    violations = _scan(
        tmp_path,
        ".agents/shared/example.py",
        'MESSAGE = "한국어 메시지"\n',
    )
    assert len(violations) == 1


def test_agents_shell_file_is_tier1_scanned(tmp_path: Path) -> None:
    """AGENTS.md lists `.agents/**`, including shell hook helpers."""
    target = tmp_path / ".agents" / "shared" / "harness-python.sh"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("#!/usr/bin/env sh\n# 한국어 rationale\n", encoding="utf-8")

    assert CHECKER.filter_to_tier1([target], repo_root=tmp_path) == [target]
    violations = CHECKER.find_violations(target, repo_root=tmp_path)
    assert len(violations) == 1


def test_codex_rules_file_is_tier1_scanned(tmp_path: Path) -> None:
    """AGENTS.md lists `.codex/rules/**`, including non-Markdown rule files."""
    target = tmp_path / ".codex/rules/example.rules"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text('justification = "한국어 rationale"\n', encoding="utf-8")

    assert CHECKER.filter_to_tier1([target], repo_root=tmp_path) == [target]
    violations = CHECKER.find_violations(target, repo_root=tmp_path)
    assert len(violations) == 1


# ---------------------------------------------------------------------------
# 9. Drift test — TIER1_GLOBS vs AGENTS.md § Language Policy bullet list
# ---------------------------------------------------------------------------


def _extract_policy_paths_from_agents_md() -> set[str]:
    """Parse AGENTS.md § Language Policy → Tier 1 paths bullet list.

    Returns the set of distinct path tokens (each backtick-quoted entry).
    """
    text = (REPO_ROOT / "AGENTS.md").read_text(encoding="utf-8")
    match = re.search(
        r"### Tier 1 paths.*?###",
        text,
        flags=re.DOTALL,
    )
    assert match, "AGENTS.md § Language Policy → Tier 1 paths section not found"
    section = match.group(0)
    bullet_lines = "\n".join(
        line for line in section.splitlines() if line.startswith("- ")
    )
    repo_root_markers = (
        "AGENTS.md",
        "CLAUDE.md",
        "CONTRIBUTING.md",
        "CODE_OF_CONDUCT.md",
        "SECURITY.md",
        "docs/",
        ".claude/",
        ".codex/",
        ".agents/",
        ".github/",
    )
    return {
        token
        for token in re.findall(r"`([^`]+)`", bullet_lines)
        if token.startswith(repo_root_markers)
    }


def test_tier1_globs_match_agents_md_policy_bullets() -> None:
    """Drift guard: the TIER1_GLOBS in the checker must cover every
    path token listed in AGENTS.md § Language Policy → Tier 1 paths,
    and vice versa after normalising prose-level directory bullets to
    checker-level file globs.

    Allow either form: a glob may be present in the policy (e.g.
    ``docs/ai/shared/**``) or in TIER1_GLOBS as a parameterised glob
    (e.g. ``docs/ai/shared/**/*.md``). A simple normalisation makes
    them comparable.
    """
    policy_paths = _extract_policy_paths_from_agents_md()
    glob_paths = set(CHECKER.TIER1_GLOBS)

    def _normalize(path: str) -> str:
        # Drop trailing /** and /**/*.* extensions for comparison.
        normalized = re.sub(r"/\*\*(/\*\*?)?(\.[a-z]+)?$", "", path)
        normalized = re.sub(r"/\*\*$", "", normalized)
        return normalized.rstrip("/")

    policy_normalized = {_normalize(p) for p in policy_paths}
    glob_normalized = {_normalize(g) for g in glob_paths}

    assert policy_normalized == glob_normalized


def _representative_path_for_glob(pattern: str) -> str:
    if "*" not in pattern:
        return pattern

    suffix_samples = {
        "/**/*.md": "/sample.md",
        "/**/*.py": "/sample.py",
        "/**/*.sh": "/sample.sh",
        "/**/*.yml": "/sample.yml",
        "/**/*.yaml": "/sample.yaml",
        "/**/*": "/sample.txt",
    }
    for suffix, sample in suffix_samples.items():
        if pattern.endswith(suffix):
            return pattern[: -len(suffix)] + sample

    raise AssertionError(f"Unsupported TIER1_GLOBS pattern shape: {pattern}")


def test_pre_commit_regex_covers_canonical_anchor_paths() -> None:
    """R132-IMPL.2 drift guard: the pre-commit `files:` regex must match
    every canonical anchor path that TIER1_GLOBS covers. Without this
    test, the YAML regex can silently drift from the checker's globs and
    contributors would commit Korean prose to a Tier 1 file that the
    pre-commit hook never opens.

    Strategy: read the YAML, extract the regex from the
    `tier1-language-policy` hook, and compile it against a generated
    representative path for every TIER1_GLOBS entry.
    """
    config_text = (REPO_ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8")
    match = re.search(
        r"id:\s*tier1-language-policy.*?files:\s*'([^']+)'",
        config_text,
        flags=re.DOTALL,
    )
    assert match, (
        "tier1-language-policy hook with `files:` regex not found in .pre-commit-config.yaml"
    )
    files_regex = re.compile(match.group(1))

    representative_paths = [
        _representative_path_for_glob(pattern) for pattern in CHECKER.TIER1_GLOBS
    ]
    not_matched = [p for p in representative_paths if not files_regex.match(p)]
    assert not not_matched, (
        "pre-commit `files:` regex does not match these canonical anchor "
        f"paths (drift from TIER1_GLOBS): {not_matched}"
    )


# ---------------------------------------------------------------------------
# 10. Working-tree sanity check
# ---------------------------------------------------------------------------


def test_working_tree_has_zero_violations() -> None:
    """The whole working tree must currently pass the checker — this
    test is the live regression that fails the moment a contributor
    introduces Korean prose into a Tier 1 path."""
    paths = CHECKER.discover_tier1_paths(REPO_ROOT)
    all_violations = []
    for path in paths:
        all_violations.extend(CHECKER.find_violations(path, repo_root=REPO_ROOT))
    if all_violations:
        formatted = "\n".join(v.format() for v in all_violations[:20])
        pytest.fail(
            f"{len(all_violations)} Tier 1 Language Policy violations found "
            f"in the working tree (first 20 shown):\n{formatted}"
        )
