"""Pin the markdown link checker's behaviour, and the reason it is allowed to block.

`tools/check_doc_links.py` is a blocking pre-commit hook, which `project-dna.md`
§0 reserves for facts rather than judgement ("the harness nudges; humans and CI
decide"). `/execute-plan` § Advisory-First Enforcement names the price of
crossing that line: tests, and no broad false positives. This file is that price.

Two groups of tests carry the weight:

- **`TestNoFalsePositives`** is the blocking argument. Each case is a construct
  that *looks* like a broken link and must not be reported: a link inside a
  fenced block, a regex inside inline backticks (AGENTS.md L110 is the live one
  — `^\\s*\\[(trivial|hotfix|exploration)\\](?:\\s|$)` reads as a link to a
  program), YAML frontmatter, an external URL, a `#L10` line reference. Delete one
  of these and the hook starts blocking legitimate commits.
- **`TestRealRepository`** pins that the hook is actually *looking* at something.
  "0 broken" and "nothing scanned" print identically — the illusion pyright's
  `**/.*` exclude sustained for two releases (project-dna §7) — so the scan
  asserts a floor on links checked, not just an empty violation list.

The rest pins the failure modes this checker exists for: relative depth counted
from the wrong directory (#405 shipped eight of those), a renamed heading
orphaning inbound anchors (#79 shipped two, undetected for four months), and a
case-only mismatch that resolves on macOS and 404s on Linux CI.
"""

from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
TOOL_PATH = REPO_ROOT / "tools" / "check_doc_links.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("check_doc_links", TOOL_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_doc_links"] = module
    spec.loader.exec_module(module)
    return module


cdl = _load_module()


def _checker(tmp_path: Path, tracked: dict[str, str]):
    """Materialise `tracked` (repo-relative path -> content) and index all of it."""
    for rel, content in tracked.items():
        target = tmp_path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    index = cdl.RepoIndex.from_paths(tracked)
    return cdl.DocLinkChecker(index, repo_root=tmp_path)


class TestPathResolution:
    def test_resolving_relative_link_is_clean(self, tmp_path):
        checker = _checker(
            tmp_path,
            {
                "docs/guide.md": "See [ADR](../docs/history/001.md).\n",
                "docs/history/001.md": "# One\n",
            },
        )
        # `docs/guide.md` + `../docs/history/001.md` -> `docs/history/001.md`.
        assert checker.check_file("docs/guide.md") == []

    def test_one_level_too_shallow_is_flagged(self, tmp_path):
        """The #405 shape: a file at depth 4 pointing at `../../history/`.

        `docs/ai/shared/skills/` minus two levels is `docs/ai/`, not `docs/`.
        Eight links of exactly this form shipped through three review rounds.
        """
        checker = _checker(
            tmp_path,
            {
                "docs/ai/shared/skills/fix-bug.md": (
                    "See [ADR 054](../../history/054-boundary.md).\n"
                ),
                "docs/history/054-boundary.md": "# ADR 054\n",
            },
        )

        violations = checker.check_file("docs/ai/shared/skills/fix-bug.md")

        assert len(violations) == 1
        assert violations[0].line_number == 1
        assert "docs/ai/history/054-boundary.md" in violations[0].reason

    def test_correct_depth_from_same_file_is_clean(self, tmp_path):
        checker = _checker(
            tmp_path,
            {
                "docs/ai/shared/skills/fix-bug.md": (
                    "See [ADR 054](../../../history/054-boundary.md).\n"
                ),
                "docs/history/054-boundary.md": "# ADR 054\n",
            },
        )
        assert checker.check_file("docs/ai/shared/skills/fix-bug.md") == []

    def test_directory_target_resolves(self, tmp_path):
        """34 links in this repository point at directories (`examples/`, `_env/`)."""
        checker = _checker(
            tmp_path,
            {
                "README.md": "Browse [examples](examples/) and [env](_env).\n",
                "examples/todo/main.py": "",
                "_env/local.env.example": "",
            },
        )
        assert checker.check_file("README.md") == []

    def test_case_only_mismatch_is_flagged(self, tmp_path):
        """The reason the git index is the authority rather than `Path.exists()`.

        macOS APFS is case-insensitive by default, so this link opens locally and
        404s on GitHub and on Linux CI. A filesystem check cannot see it.
        """
        checker = _checker(
            tmp_path,
            {
                "README.md": "See [readme](docs/Readme.md).\n",
                "docs/readme.md": "# Readme\n",
            },
        )

        violations = checker.check_file("README.md")

        assert len(violations) == 1
        assert "docs/Readme.md" in violations[0].reason

    def test_untracked_but_present_file_is_flagged(self, tmp_path):
        """A file on disk but not in the index is dead for every other reader."""
        (tmp_path / "docs").mkdir(parents=True, exist_ok=True)
        (tmp_path / "docs/scratch.md").write_text("# Scratch\n", encoding="utf-8")
        checker = _checker(tmp_path, {"docs/guide.md": "[s](scratch.md)\n"})

        violations = checker.check_file("docs/guide.md")

        assert len(violations) == 1
        assert "not in the git index" in violations[0].reason

    def test_escaping_the_repository_root_is_flagged(self, tmp_path):
        checker = _checker(tmp_path, {"README.md": "[up](../outside.md)\n"})

        violations = checker.check_file("README.md")

        assert len(violations) == 1
        assert "escapes the repository root" in violations[0].reason

    def test_root_absolute_target_is_flagged(self, tmp_path):
        """`/docs/x.md` renders against a site root, not the repository root."""
        checker = _checker(
            tmp_path,
            {"README.md": "[abs](/docs/guide.md)\n", "docs/guide.md": "# Guide\n"},
        )

        violations = checker.check_file("README.md")

        assert len(violations) == 1
        assert "root-absolute" in violations[0].reason

    def test_html_href_and_img_src_are_checked(self, tmp_path):
        """README.md carries four relative links in HTML, not Markdown, syntax."""
        checker = _checker(
            tmp_path,
            {
                "README.md": (
                    '<a href="docs/README.ko.md">KO</a>\n'
                    '<img src="docs/assets/missing.png" alt="x">\n'
                ),
                "docs/README.ko.md": "# KO\n",
            },
        )

        violations = checker.check_file("README.md")

        assert len(violations) == 1
        assert violations[0].line_number == 2

    def test_reference_definition_target_is_checked(self, tmp_path):
        checker = _checker(tmp_path, {"docs/guide.md": "[adr]: history/001.md\n"})

        violations = checker.check_file("docs/guide.md")

        assert len(violations) == 1
        assert "docs/history/001.md" in violations[0].reason

    def test_balanced_parentheses_in_a_target_are_extracted(self, tmp_path):
        """CommonMark §6.3 allows balanced parens in a destination. A destination
        pattern that stops at the first `(` does not truncate the target — the
        whole match fails and the link is skipped in silence, so this asserts the
        broken case is *reported*, which a truncating pattern cannot do."""
        checker = _checker(
            tmp_path,
            {
                "README.md": (
                    "[ok](docs/notes_(draft).md) and [dead](docs/gone_(old).md)\n"
                ),
                "docs/notes_(draft).md": "# Notes\n",
            },
        )

        violations = checker.check_file("README.md")

        assert len(violations) == 1
        assert "docs/gone_(old).md" in violations[0].reason

    def test_percent_encoded_target_is_decoded(self, tmp_path):
        checker = _checker(
            tmp_path,
            {"README.md": "[x](docs/a%20b.md)\n", "docs/a b.md": "# A B\n"},
        )
        assert checker.check_file("README.md") == []


class TestAnchors:
    def test_matching_heading_is_clean(self, tmp_path):
        checker = _checker(
            tmp_path,
            {
                "CLAUDE.md": "See [policy](AGENTS.md#language-policy).\n",
                "AGENTS.md": "# Rules\n\n## Language Policy\n",
            },
        )
        assert checker.check_file("CLAUDE.md") == []

    def test_renamed_heading_orphans_the_anchor(self, tmp_path):
        """The #79 failure: README's `## AI-Native Development` became
        `## AI collaboration harness` and two inbound anchors went dead for four
        months. Only a full-repo scan can see this — the commit that renames the
        heading does not touch the files that point at it."""
        checker = _checker(
            tmp_path,
            {
                "docs/ai-development.md": "[README](../README.md#ai-native-development)\n",
                "README.md": "# Blueprint\n\n## AI collaboration harness\n",
            },
        )

        violations = checker.check_file("docs/ai-development.md")

        assert len(violations) == 1
        assert "#ai-native-development" in violations[0].reason

    def test_same_file_anchor_is_checked(self, tmp_path):
        checker = _checker(
            tmp_path,
            {"README.md": "[jump](#why-this-blueprint)\n\n## Why this blueprint\n"},
        )
        assert checker.check_file("README.md") == []

    def test_same_file_anchor_missing_is_flagged(self, tmp_path):
        checker = _checker(tmp_path, {"README.md": "[jump](#nope)\n\n## Why\n"})

        violations = checker.check_file("README.md")

        assert len(violations) == 1
        assert "this file" in violations[0].reason

    def test_html_id_anchor_is_accepted(self, tmp_path):
        checker = _checker(
            tmp_path,
            {"README.md": '<a id="top"></a>\n\n[back](#top)\n'},
        )
        assert checker.check_file("README.md") == []

    def test_duplicate_headings_get_github_suffixes(self):
        anchors = cdl.heading_anchors("## Notes\n\n## Notes\n\n## Notes\n")
        assert anchors == frozenset({"notes", "notes-1", "notes-2"})

    def test_headings_inside_fences_are_not_anchors(self):
        anchors = cdl.heading_anchors(
            "# Real\n\n```python\n# src/_core/services/rag.py\n```\n"
        )
        assert anchors == frozenset({"real"})

    @pytest.mark.parametrize(
        ("heading", "slug"),
        [
            ("Try it in 60 seconds", "try-it-in-60-seconds"),
            (
                "AI use case: document QA (`src/docs/`)",
                "ai-use-case-document-qa-srcdocs",
            ),
            ("Data flow — Write (`POST` / `PUT`)", "data-flow--write-post--put"),
            ("**Bold** and _italic_", "bold-and-italic"),
            ("§0. Project Scale", "0-project-scale"),
            # Non-ASCII letters are alphanumeric and survive: docs/README.ko.md
            # links to its own Korean headings this way.
            ("한눈에 보는 아키텍처", "한눈에-보는-아키텍처"),
        ],
    )
    def test_slugify_matches_github(self, heading, slug):
        assert cdl.slugify_heading(heading) == slug


class TestNoFalsePositives:
    """Every case here is why this hook is allowed to block a commit."""

    def test_links_inside_fenced_blocks_are_ignored(self, tmp_path):
        checker = _checker(
            tmp_path,
            {"docs/guide.md": "```markdown\nSee [ADR](../nowhere/001.md).\n```\n"},
        )
        assert checker.check_file("docs/guide.md") == []

    def test_links_inside_tilde_fenced_blocks_are_ignored(self, tmp_path):
        """This is the case that pins `_strip_fenced_blocks` specifically.

        A backtick fence is *also* swallowed by the inline-code-span pass, since
        ``` is itself a backtick run — so a backtick-only test passes even with
        fence handling removed. A `~~~` fence is invisible to that pass, so only
        the fence stripper keeps it out.
        """
        checker = _checker(
            tmp_path,
            {"docs/guide.md": "~~~markdown\nSee [ADR](../nowhere/001.md).\n~~~\n"},
        )
        assert checker.check_file("docs/guide.md") == []

    def test_fences_indented_inside_a_list_item_are_ignored(self, tmp_path):
        """`tools/check_language_policy.py` deliberately stops at CommonMark's
        3-space fence indentation; this checker does not. Over-stripping loses a
        link (a false negative); under-stripping blocks a legitimate commit."""
        checker = _checker(
            tmp_path,
            {
                "docs/guide.md": (
                    "1. Example:\n\n"
                    "       ```text\n"
                    "       See [ADR](../nowhere/001.md).\n"
                    "       ```\n"
                )
            },
        )
        assert checker.check_file("docs/guide.md") == []

    def test_inline_code_is_ignored(self, tmp_path):
        r"""AGENTS.md L110 is the live case. The token-recognition regex
        `^\s*\[(trivial|hotfix|exploration)\](?:\s|$)` parses as a link whose
        target is `?:\s|$`, and a naive sweep reports it in four files."""
        checker = _checker(
            tmp_path,
            {
                "AGENTS.md": (
                    "Recognition regex: "
                    r"`^\s*\[(trivial|hotfix|exploration)\](?:\s|$)`."
                    "\n"
                )
            },
        )
        assert checker.check_file("AGENTS.md") == []

    def test_yaml_frontmatter_is_ignored(self, tmp_path):
        checker = _checker(
            tmp_path,
            {
                ".claude/skills/fix-bug/SKILL.md": (
                    "---\n"
                    "name: fix-bug\n"
                    "description: See [rules](../nowhere/rules.md)\n"
                    "---\n\n"
                    "# Fix Bug\n"
                )
            },
        )
        assert checker.check_file(".claude/skills/fix-bug/SKILL.md") == []

    @pytest.mark.parametrize(
        "target",
        [
            "https://github.com/Mr-DooSun/fastapi-agent-blueprint/issues/18",
            "http://127.0.0.1:8001/admin",
            "mailto:security@example.com",
        ],
    )
    def test_external_targets_are_skipped(self, tmp_path, target):
        checker = _checker(tmp_path, {"README.md": f"[x]({target})\n"})
        assert checker.check_file("README.md") == []

    def test_line_number_fragments_are_skipped(self, tmp_path):
        """`#L42` is a GitHub UI feature, not a heading."""
        checker = _checker(
            tmp_path,
            {
                "docs/guide.md": "[line](../src/main.py#L42) and [self](#L7)\n",
                "src/main.py": "",
            },
        )
        assert checker.check_file("docs/guide.md") == []

    def test_fragment_on_non_markdown_target_is_skipped(self, tmp_path):
        checker = _checker(
            tmp_path,
            {
                "docs/guide.md": "[cfg](../pyproject.toml#tool-ruff)\n",
                "pyproject.toml": "",
            },
        )
        assert checker.check_file("docs/guide.md") == []

    def test_links_inside_html_comments_are_ignored(self, tmp_path):
        """README.md keeps a regeneration note above its demo GIF. A commented-out
        link is not a link, and a stale one must not block a commit."""
        checker = _checker(
            tmp_path,
            {"README.md": "<!-- was [old](docs/gone.md) -->\n\nText.\n"},
        )
        assert checker.check_file("README.md") == []

    def test_repository_root_target_resolves(self, tmp_path):
        """`../` from a subdirectory and `./` from the root both normalise to `.`,
        which is a real directory but is in no file list."""
        checker = _checker(
            tmp_path,
            {"docs/guide.md": "[root](../) and [here](./)\n", "README.md": "# R\n"},
        )
        assert checker.check_file("docs/guide.md") == []

    def test_a_tracked_file_missing_from_the_working_tree_is_skipped(self, tmp_path):
        """`git ls-files` lists the index, so an unstaged `rm docs/x.md` leaves a
        path this hook would otherwise report as unreadable — on every commit, for
        a git state that is not a link defect."""
        index = cdl.RepoIndex.from_paths(["docs/guide.md", "docs/gone.md"])
        checker = cdl.DocLinkChecker(index, repo_root=tmp_path)

        assert checker.check_file("docs/gone.md") == []

    def test_anchor_into_a_file_missing_from_the_working_tree_is_skipped(
        self, tmp_path
    ):
        """Reading no headings is not the same as a file having none: an
        unreadable target would otherwise fail every anchor pointing into it."""
        (tmp_path / "docs").mkdir(parents=True, exist_ok=True)
        (tmp_path / "docs/guide.md").write_text(
            "[x](gone.md#section)\n", encoding="utf-8"
        )
        # `docs/gone.md` is in the index but was never written to disk.
        index = cdl.RepoIndex.from_paths(["docs/guide.md", "docs/gone.md"])
        checker = cdl.DocLinkChecker(index, repo_root=tmp_path)

        assert checker.check_file("docs/guide.md") == []

    def test_glossary_style_reference_definition_is_ignored(self, tmp_path):
        """`[Term]: word` is a legal link definition whose destination is a word,
        not a path. Only definitions that look like paths are resolved."""
        checker = _checker(tmp_path, {"docs/guide.md": "[Ledger]: bookkeeping\n"})
        assert checker.check_file("docs/guide.md") == []

    def test_setext_heading_provides_an_anchor(self, tmp_path):
        """Cross-review finding. Recognising only ATX headings reports a live
        anchor as broken; the repository has no setext headings today, so this
        would have been the first contributor to write one."""
        checker = _checker(
            tmp_path,
            {"README.md": "[jump](#hello-world)\n\nHello World\n===========\n"},
        )
        assert checker.check_file("README.md") == []

    def test_horizontal_rule_after_a_blank_line_is_not_a_setext_heading(self, tmp_path):
        """The other side of that fix: `---` under a *blank* line is a rule, and
        this repository uses hundreds of them."""
        checker = _checker(
            tmp_path, {"README.md": "Some prose.\n\n---\n\n[x](#some-prose)\n"}
        )

        violations = checker.check_file("README.md")

        assert len(violations) == 1
        assert "#some-prose" in violations[0].reason

    @pytest.mark.parametrize("quote", ['"', "'"])
    def test_html_attributes_accept_either_quote_style(self, tmp_path, quote):
        """Cross-review finding, in both directions: a single-quoted `id='top'`
        was reported as a missing anchor, and a single-quoted `href='…'` was
        skipped entirely."""
        checker = _checker(
            tmp_path,
            {
                "README.md": (
                    f"<a id={quote}top{quote}></a>\n"
                    f"[back](#top)\n"
                    f"<a href={quote}docs/guide.md{quote}>g</a>\n"
                ),
                "docs/guide.md": "# G\n",
            },
        )
        assert checker.check_file("README.md") == []

    def test_query_string_addresses_the_same_file(self, tmp_path):
        """Cross-review finding. GitHub's `?plain=1` renders the source view of
        the same path; it is not part of the filename."""
        checker = _checker(
            tmp_path,
            {"README.md": "[guide](docs/guide.md?plain=1)\n", "docs/guide.md": "# G\n"},
        )
        assert checker.check_file("README.md") == []

    def test_protocol_relative_url_is_not_a_root_absolute_path(self, tmp_path):
        """Cross-review finding. `//example.com/x` is an external URL that merely
        starts with a slash; it carries no scheme for `_SCHEME_RE` to catch."""
        checker = _checker(tmp_path, {"README.md": "[ex](//example.com/docs)\n"})
        assert checker.check_file("README.md") == []

    def test_backslash_escaped_punctuation_is_unescaped(self, tmp_path):
        """Cross-review finding. CommonMark §2.4 — the destination addresses
        `docs/notes(draft).md`, not a filename containing backslashes."""
        checker = _checker(
            tmp_path,
            {
                "README.md": "[notes](docs/notes\\(draft\\).md)\n",
                "docs/notes(draft).md": "# N\n",
            },
        )
        assert checker.check_file("README.md") == []


class TestRepoIndex:
    def test_from_paths_derives_parent_directories(self):
        index = cdl.RepoIndex.from_paths(["docs/ai/shared/project-dna.md"])
        assert index.directories == frozenset({"docs", "docs/ai", "docs/ai/shared"})

    def test_markdown_files_are_sorted_and_filtered(self):
        index = cdl.RepoIndex.from_paths(["b.md", "a.md", "c.py"])
        assert index.markdown_files() == ["a.md", "b.md"]

    def test_empty_git_index_raises_rather_than_reporting_clean(self, tmp_path):
        """An empty index must not print the same thing as a clean repository."""
        subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)  # noqa: S603, S607

        with pytest.raises(RuntimeError, match="git ls-files returned nothing"):
            cdl.RepoIndex.from_git(tmp_path)


class TestRealRepository:
    """The checker's own repository must pass — and must be seen to be scanned."""

    def test_repository_has_no_broken_links(self):
        result = cdl.scan_repository(repo_root=REPO_ROOT)
        detail = "\n".join(violation.format() for violation in result.violations)
        assert result.violations == [], f"broken markdown links:\n{detail}"

    def test_scan_actually_checks_a_meaningful_number_of_links(self):
        """ "0 broken" and "nothing scanned" print identically.

        The tree this shipped on had 192 markdown files, 646 relative targets and
        86 anchors. The floors are deliberately loose — they exist to fail when
        extraction silently stops working, not to be re-baselined on every doc PR.
        """
        result = cdl.scan_repository(repo_root=REPO_ROOT)

        assert result.files_scanned >= 150
        assert result.path_links_checked >= 400
        assert result.fragments_checked >= 50


class TestPreCommitWiring:
    """The checker is only enforcement if the hook actually runs it, blocking,
    over the whole tree. CI runs `pre-commit run --all-files`, so this wiring is
    also what makes it a CI gate."""

    BOUNDARY = re.compile(r"^[ \t]*(?:#|- id:|- repo:)")

    def _hook_body(self) -> str:
        """The `doc-links` entry's own lines: from its `- id:` to the next hook,
        repo, or comment. Scanned rather than regex-captured so an adjacent
        hook's fields cannot leak in and quietly satisfy an assertion."""
        config = (REPO_ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8")
        lines = config.splitlines()
        starts = [
            i for i, line in enumerate(lines) if line.strip() == "- id: doc-links"
        ]
        assert starts, "doc-links hook not found in .pre-commit-config.yaml"
        body: list[str] = []
        for line in lines[starts[0] + 1 :]:
            if self.BOUNDARY.match(line):
                break
            body.append(line)
        return "\n".join(body)

    def test_hook_invokes_the_checker(self):
        assert "tools/check_doc_links.py" in self._hook_body()

    def test_hook_scans_the_whole_tree(self):
        """`pass_filenames: false` + `always_run: true`. A changed-files hook
        cannot catch a heading rename orphaning anchors elsewhere."""
        body = self._hook_body()
        assert "pass_filenames: false" in body
        assert "always_run: true" in body

    def test_hook_is_blocking(self):
        """No `stages: [manual]` (the retired mypy hook's failure mode: nothing
        ever ran it) and no `verbose: true`-only advisory posture like
        migration-safety, which exits 0 by design."""
        body = self._hook_body()
        assert "stages:" not in body
        assert "verbose:" not in body
