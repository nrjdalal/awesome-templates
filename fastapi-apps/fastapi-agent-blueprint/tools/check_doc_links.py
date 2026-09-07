"""Markdown link checker: relative targets must resolve, anchors must exist (#408).

Every relative link in a git-tracked ``*.md`` file is resolved against the git
index, and every ``#fragment`` pointing at a Markdown file is resolved against
that file's headings.

Why this exists as a checker rather than as three one-character fixes: the
governance documents in this repository are becoming link-dense, and a document
whose whole function is to point at its authorities can point at nothing without
emitting any signal. #405 added 19 relative links to one shared skill file; eight
of them — every pointer the file made to an ADR or to ``AGENTS.md`` — resolved one
directory level too shallow, and passed three cross-tool review rounds,
``pre-commit``, ``pyright``, ``tools/check_language_policy.py`` and all nine CI
jobs before a manual audit caught them. That is the same shape as the two lessons
already recorded in ``.claude/rules/project-status.md``: *a stale allow-list fails
nothing*, and *"0 errors" and "nothing checked" print identically*.

Scope: **every git-tracked ``*.md`` file in the repository**, with no allow-list.
Narrowing to ``docs/`` was considered and rejected — 150 of the 646 relative links
live outside it, including 27 in ``AGENTS.md`` and 23 under ``.claude/``, which are
exactly the governance authorities the failure mode targets. More importantly, a
scoped path list is itself a drift generator: this repository has been bitten
twice (the pyright package allow-list in #375, and the ``project-dna.md`` bullet
describing it, both stale and both failing nothing). "Every Markdown file" needs
no list, so it cannot go stale.

Resolution authority is the **git index**, not ``Path.exists()``:

- It is case-sensitive on every platform. macOS APFS is case-insensitive by
  default, so ``docs/History/x.md`` resolves locally and 404s on Linux CI — a
  silent divergence this repository has no other guard against.
- It is what a reader on GitHub actually sees: GitHub renders from the tree, so an
  untracked local file cannot mask a link that is dead for everyone else.
- ``git ls-files`` reads the *index*, so a file staged in the same commit as the
  link that points at it resolves correctly.

Checks performed:

1. **Path targets.** Inline links ``[t](path)``, images ``![t](path)``, reference
   definitions ``[label]: path``, and HTML ``<a href="...">`` / ``<img src="...">``.
   A target resolving to a tracked file *or* a tracked directory passes.
2. **Fragments.** ``file.md#anchor`` and same-file ``#anchor`` are resolved against
   the target's ATX and setext headings (GitHub slug algorithm) plus any explicit
   HTML ``id=`` / ``name=`` anchor. This is the check that catches a renamed
   heading silently orphaning every pointer to it; it found two such orphans on
   the day it was written.

Deliberately out of scope, so that neither is mistaken for coverage:

- **External URLs.** Anything with a scheme is skipped. Network checks are
  non-deterministic, and a link-rot failure would redden a PR that changed
  nothing — the same reason ``pip-audit`` is advisory (project-dna §7).
- **Fragments on non-Markdown targets.** ``script.py#L10`` and bare ``#L10``
  line references are skipped: they are GitHub UI features, not headings.
- **Shortcut/collapsed reference links** (``[label]`` / ``[label][]``). Only the
  *definition* line's target is validated, which is where the path actually lives;
  matching the usage site would need full CommonMark parsing and would false-
  positive on ordinary bracketed prose.

Used by:
- ``.pre-commit-config.yaml`` ``doc-links`` hook (blocking; full-repo scan, so a
  heading rename in one file is caught against pointers in files this commit did
  not touch — a changed-files hook cannot see that).
- ``tests/unit/tools/test_check_doc_links.py``.
- Ad-hoc dry-run: ``python3 tools/check_doc_links.py [FILE ...]`` (no argv = full
  repository scan).
"""

from __future__ import annotations

import posixpath
import re
import subprocess
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote

REPO_ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Markdown noise removal
# ---------------------------------------------------------------------------
# All three helpers preserve line numbering by blanking rather than deleting, so
# a Violation can still name the line a link was written on.

_FRONTMATTER_FENCE_RE = re.compile(r"^---[ \t]*$")

# Fences are matched at ANY indentation, unlike tools/check_language_policy.py,
# which deliberately stops at CommonMark's 3-space limit. The asymmetry is
# intentional: over-stripping here loses a link inside a code block (a false
# negative, and this hook blocks commits), while under-stripping turns an
# illustrative snippet into a blocked commit. AGENTS.md L110 is the live example
# — `^\s*\[(trivial|hotfix|exploration)\](?:\s|$)` is a regex, not a link.
_FENCE_RE = re.compile(r"^[ \t]*(?P<marker>`{3,}|~{3,})")

# Lazy same-length backtick run. Over-matching only ever hides a link.
_CODE_SPAN_RE = re.compile(r"(?P<ticks>`+)(?P<body>.+?)(?P=ticks)", re.DOTALL)


def _blank_match(match: re.Match[str]) -> str:
    """Replace a match with spaces, preserving its newlines (and line numbers)."""
    return re.sub(r"[^\n]", " ", match.group(0))


def _strip_frontmatter(text: str) -> str:
    """Blank a leading YAML frontmatter block (``.claude/skills/*/SKILL.md``)."""
    lines = text.splitlines(keepends=True)
    if not lines or not _FRONTMATTER_FENCE_RE.match(lines[0].rstrip("\n")):
        return text
    for index in range(1, len(lines)):
        if _FRONTMATTER_FENCE_RE.match(lines[index].rstrip("\n")):
            blanked = [
                "\n" if line.endswith("\n") else "" for line in lines[: index + 1]
            ]
            return "".join(blanked) + "".join(lines[index + 1 :])
    return text


def _strip_fenced_blocks(text: str) -> str:
    """Blank fenced code blocks. A fence closes only on the same marker character,
    repeated at least as many times (CommonMark §4.5)."""
    out: list[str] = []
    open_marker: str | None = None
    for raw in text.splitlines():
        match = _FENCE_RE.match(raw)
        marker = match.group("marker") if match else None
        if open_marker is None:
            if marker is not None:
                open_marker = marker
                out.append("")
                continue
            out.append(raw)
            continue
        # Inside a fence: only a same-char, at-least-as-long run closes it.
        if (
            marker is not None
            and marker[0] == open_marker[0]
            and len(marker) >= len(open_marker)
            and raw.strip() == marker
        ):
            open_marker = None
        out.append("")
    return "\n".join(out)


# A commented-out link is not a link. README.md keeps a regeneration note above
# its demo GIF; a future one holding a stale path must not block a commit.
_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)


def _strip_markdown_noise(text: str) -> str:
    stripped = _strip_fenced_blocks(_strip_frontmatter(text))
    stripped = _HTML_COMMENT_RE.sub(_blank_match, stripped)
    return _CODE_SPAN_RE.sub(_blank_match, stripped)


# ---------------------------------------------------------------------------
# Link extraction
# ---------------------------------------------------------------------------
# The label may contain one level of nested brackets so `[![alt](img)](target)`
# extracts `target`. A destination is either <bracketed> or a bare run without
# whitespace, allowing one level of balanced parentheses (CommonMark §6.3). Note
# what the narrower `[^()\s]*` spelling actually does to `[x](docs/a_(b).md)`: the
# whole match fails, so the link is skipped in silence rather than truncated —
# a missed broken link, not a false positive.
_INLINE_LINK_RE = re.compile(
    r"(?<!\\)!?\[(?:[^\[\]]|\[[^\[\]]*\])*\]"
    r"\(\s*(?P<target><[^<>]*>|(?:[^()\s]|\([^()\s]*\))*)"
    r'(?:\s+"[^"]*")?\s*\)'
)
# A definition's destination is a single token, so `[Term]: a prose definition`
# does not match at all. `_looks_like_a_path` covers the one-word residue.
_REFERENCE_DEF_RE = re.compile(
    r'^[ ]{0,3}\[[^\]]+\]:[ \t]+(?P<target><[^<>]*>|\S+)(?:[ \t]+["(\'].*)?[ \t]*$'
)
# Both quote styles: `<a href='x'>` is valid HTML, and accepting only double
# quotes silently skipped it — the mirror of the anchor-side bug that reported a
# single-quoted `id='top'` as missing.
_HTML_HREF_RE = re.compile(
    r"""<a\b[^>]*?\shref=["'](?P<target>[^"']*)["']""", re.IGNORECASE
)
_HTML_SRC_RE = re.compile(
    r"""<img\b[^>]*?\ssrc=["'](?P<target>[^"']*)["']""", re.IGNORECASE
)

_SCHEME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.\-]*:")
_LINE_FRAGMENT_RE = re.compile(r"^L\d+(?:-L\d+)?$", re.IGNORECASE)
# CommonMark §2.4: any ASCII punctuation may be backslash-escaped in a
# destination, so `docs/notes\(draft\).md` addresses `docs/notes(draft).md`.
_BACKSLASH_ESCAPE_RE = re.compile(r"\\([!-/:-@\[-`{-~])")


@dataclass(frozen=True)
class Link:
    target: str
    line_number: int
    line_content: str


def _looks_like_a_path(target: str) -> bool:
    """Reference definitions only. `[Term]: glossary` is a legal definition whose
    destination is a word, not a file; requiring a separator or an extension keeps
    a glossary line from blocking a commit."""
    return "/" in target or "." in target or target.startswith("#")


def extract_links(text: str) -> list[Link]:
    """Return every link destination in `text`, code and frontmatter removed."""
    cleaned = _strip_markdown_noise(text)
    raw_lines = text.splitlines()
    links: list[Link] = []
    for index, line in enumerate(cleaned.splitlines(), start=1):
        source_line = raw_lines[index - 1] if index <= len(raw_lines) else line
        for pattern in (
            _INLINE_LINK_RE,
            _REFERENCE_DEF_RE,
            _HTML_HREF_RE,
            _HTML_SRC_RE,
        ):
            for match in pattern.finditer(line):
                target = match.group("target").strip()
                if target.startswith("<") and target.endswith(">"):
                    target = target[1:-1].strip()
                if not target:
                    continue
                if pattern is _REFERENCE_DEF_RE and not _looks_like_a_path(target):
                    continue
                links.append(Link(target, index, source_line.rstrip()))
    return links


# ---------------------------------------------------------------------------
# Heading anchors (GitHub slug algorithm)
# ---------------------------------------------------------------------------

_ATX_HEADING_RE = re.compile(r"^[ ]{0,3}#{1,6}[ \t]+(?P<text>.*?)[ \t]*#*[ \t]*$")
# A setext underline turns the paragraph line above it into a heading. The repo
# has none today, but missing them means reporting a live anchor as broken.
_SETEXT_UNDERLINE_RE = re.compile(r"^[ ]{0,3}(?:=+|-+)[ \t]*$")
# Lines that cannot be setext heading text: another heading, a list item, a
# blockquote, a table row, or a horizontal rule's own blank surroundings.
_NOT_SETEXT_TEXT_RE = re.compile(r"^[ ]{0,3}(?:#|>|\||[-*+=][ \t]|\d+[.)][ \t])")
_HTML_ANCHOR_RE = re.compile(
    r"""<[a-z][a-z0-9]*\b[^>]*?\s(?:id|name)=["'](?P<value>[^"']+)["']""", re.I
)
_INLINE_IMAGE_OR_LINK_RE = re.compile(r"!?\[(?P<label>[^\]]*)\]\([^)]*\)")


def slugify_heading(heading: str) -> str:
    """GitHub's heading-to-anchor slug: render inline markup away, lowercase,
    drop everything that is not alphanumeric / hyphen / underscore, spaces to
    hyphens. Non-ASCII letters are alphanumeric and are kept (``docs/README.ko.md``
    relies on this)."""
    text = re.sub(r"`+", "", heading)
    text = _INLINE_IMAGE_OR_LINK_RE.sub(lambda m: m.group("label"), text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"[*_~]", "", text)
    return "".join(
        char if (char.isalnum() or char in "-_") else "-" if char in " \t" else ""
        for char in text.strip().lower()
    )


def heading_anchors(text: str) -> frozenset[str]:
    """Every fragment `text` offers: slugged ATX and setext headings (with
    GitHub's ``-1`` duplicate suffixes) plus explicit HTML ``id=`` / ``name=``
    anchors. Erring towards *more* anchors is the safe direction — a spurious one
    only lets a fragment resolve, while a missed one blocks a commit."""
    cleaned = _strip_fenced_blocks(_strip_frontmatter(text))
    anchors: set[str] = set()
    seen: dict[str, int] = {}

    def record(heading_text: str) -> None:
        slug = slugify_heading(heading_text)
        if not slug:
            return
        count = seen.get(slug, 0)
        seen[slug] = count + 1
        anchors.add(slug if count == 0 else f"{slug}-{count}")

    lines = cleaned.splitlines()
    for index, line in enumerate(lines):
        match = _ATX_HEADING_RE.match(line)
        if match:
            record(match.group("text"))
        elif _SETEXT_UNDERLINE_RE.match(line) and index > 0:
            previous = lines[index - 1]
            if previous.strip() and not _NOT_SETEXT_TEXT_RE.match(previous):
                record(previous)
        anchors.update(
            html_match.group("value") for html_match in _HTML_ANCHOR_RE.finditer(line)
        )
    return frozenset(anchors)


# ---------------------------------------------------------------------------
# Repository index
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RepoIndex:
    """The set of paths a link may resolve to, as repo-root-relative POSIX paths."""

    files: frozenset[str]
    directories: frozenset[str]

    @classmethod
    def from_paths(cls, paths: Iterable[str]) -> RepoIndex:
        files = frozenset(paths)
        directories: set[str] = set()
        for path in files:
            parts = path.split("/")
            for depth in range(1, len(parts)):
                directories.add("/".join(parts[:depth]))
        return cls(files=files, directories=frozenset(directories))

    @classmethod
    def from_git(cls, repo_root: Path = REPO_ROOT) -> RepoIndex:
        """Read the git index. A failure raises rather than degrading to a weaker
        check — an empty index and a clean repository must never print alike."""
        result = subprocess.run(  # noqa: S603
            ["git", "ls-files", "-z"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True,
        )
        tracked = [entry for entry in result.stdout.split("\0") if entry]
        if not tracked:
            raise RuntimeError(f"git ls-files returned nothing under {repo_root}")
        return cls.from_paths(tracked)

    def markdown_files(self) -> list[str]:
        return sorted(path for path in self.files if path.endswith(".md"))


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


@dataclass(frozen=True)
class ScanResult:
    violations: list[Violation]
    files_scanned: int
    path_links_checked: int
    fragments_checked: int


# ---------------------------------------------------------------------------
# Checker
# ---------------------------------------------------------------------------


class DocLinkChecker:
    def __init__(self, index: RepoIndex, *, repo_root: Path = REPO_ROOT) -> None:
        self._index = index
        self._repo_root = repo_root
        self._anchor_cache: dict[str, frozenset[str] | None] = {}
        self.path_links_checked = 0
        self.fragments_checked = 0

    def _anchors_of(self, rel_path: str) -> frozenset[str] | None:
        """`None` means the target could not be read, which is not the same as
        "has no headings" — a file deleted from the working tree but still in the
        index would otherwise fail every inbound anchor."""
        if rel_path not in self._anchor_cache:
            try:
                text = (self._repo_root / rel_path).read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                self._anchor_cache[rel_path] = None
            else:
                self._anchor_cache[rel_path] = heading_anchors(text)
        return self._anchor_cache[rel_path]

    def check_file(self, rel_path: str) -> list[Violation]:
        try:
            text = (self._repo_root / rel_path).read_text(encoding="utf-8")
        except FileNotFoundError:
            # Tracked but not in the working tree: a git state (an unstaged
            # deletion), not a link defect. Blocking every commit on it would be
            # exactly the false positive a blocking hook must not have.
            return []
        except (OSError, UnicodeDecodeError) as exc:
            return [
                Violation(rel_path, 0, "", f"unreadable file: {type(exc).__name__}")
            ]

        violations: list[Violation] = []
        for link in extract_links(text):
            violations.extend(self._check_link(rel_path, link))
        return violations

    def _check_link(self, rel_path: str, link: Link) -> list[Violation]:
        if _SCHEME_RE.match(link.target):
            return []
        if link.target.startswith("//"):
            # Protocol-relative external URL (`//example.com/x`), not a
            # repository path — it merely starts with a slash.
            return []
        raw_path, _, raw_fragment = link.target.partition("#")
        # GitHub accepts a query string on a repository link (`file.md?plain=1`);
        # it addresses the same file.
        raw_path = raw_path.partition("?")[0]
        path_part = _BACKSLASH_ESCAPE_RE.sub(r"\1", unquote(raw_path))
        fragment = unquote(raw_fragment)

        if path_part:
            self.path_links_checked += 1
            if path_part.startswith("/"):
                # Root-relative hrefs render against the site root, not the repo
                # root, so they are not portable between GitHub and a docs build.
                return [
                    Violation(
                        rel_path,
                        link.line_number,
                        link.line_content,
                        f"root-absolute link target `{link.target}` — use a "
                        f"repository-relative path",
                    )
                ]
            resolved = posixpath.normpath(
                posixpath.join(posixpath.dirname(rel_path), path_part.rstrip("/"))
            )
            if resolved.startswith(".."):
                return [
                    Violation(
                        rel_path,
                        link.line_number,
                        link.line_content,
                        f"link target `{link.target}` escapes the repository root",
                    )
                ]
            if (
                resolved != "."  # `./` or `../` resolving to the repository root
                and resolved not in self._index.files
                and resolved not in self._index.directories
            ):
                return [
                    Violation(
                        rel_path,
                        link.line_number,
                        link.line_content,
                        f"link target `{link.target}` does not resolve — "
                        f"`{resolved}` is not in the git index",
                    )
                ]
            target_path = resolved
        else:
            target_path = rel_path

        if not fragment or _LINE_FRAGMENT_RE.match(fragment):
            return []
        if not target_path.endswith(".md") or target_path not in self._index.files:
            return []

        anchors = self._anchors_of(target_path)
        if anchors is None:
            return []
        self.fragments_checked += 1
        if fragment in anchors:
            return []
        where = "this file" if target_path == rel_path else f"`{target_path}`"
        return [
            Violation(
                rel_path,
                link.line_number,
                link.line_content,
                f"anchor `#{fragment}` has no matching heading in {where} — "
                f"a renamed heading orphans every pointer to it",
            )
        ]

    def scan(self, rel_paths: Iterable[str]) -> ScanResult:
        violations: list[Violation] = []
        count = 0
        for rel_path in rel_paths:
            count += 1
            violations.extend(self.check_file(rel_path))
        return ScanResult(
            violations=violations,
            files_scanned=count,
            path_links_checked=self.path_links_checked,
            fragments_checked=self.fragments_checked,
        )


def scan_repository(
    argv_paths: list[str] | None = None, *, repo_root: Path = REPO_ROOT
) -> ScanResult:
    index = RepoIndex.from_git(repo_root)
    if argv_paths:
        targets = _resolve_argv_paths(argv_paths, index, repo_root)
    else:
        targets = index.markdown_files()
    return DocLinkChecker(index, repo_root=repo_root).scan(targets)


def _resolve_argv_paths(
    argv_paths: list[str], index: RepoIndex, repo_root: Path
) -> list[str]:
    resolved: list[str] = []
    for raw in argv_paths:
        candidate = Path(raw)
        if candidate.is_absolute():
            try:
                rel = candidate.resolve().relative_to(repo_root.resolve()).as_posix()
            except ValueError:
                continue
        else:
            rel = candidate.as_posix()
        if rel.endswith(".md") and rel in index.files:
            resolved.append(rel)
    return resolved


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def run(argv_paths: list[str], *, repo_root: Path = REPO_ROOT) -> int:
    result = scan_repository(argv_paths, repo_root=repo_root)

    if result.violations:
        affected = len({violation.path for violation in result.violations})
        print(
            f"Broken markdown links found "
            f"({len(result.violations)} across {affected} files):",
            file=sys.stderr,
        )
        for violation in result.violations:
            print(violation.format(), file=sys.stderr)
        print(
            "\nRelative link depth is counted from the linking file's own "
            "directory. Resolve each target from there rather than from the "
            "repository root, and check a sibling file that already links to the "
            "same place.",
            file=sys.stderr,
        )
        return 1

    # Counts are printed on success on purpose: "0 broken" and "nothing scanned"
    # must not print identically (project-dna §7, the pyright scope trap).
    print(
        f"Doc links: 0 broken across {result.files_scanned} markdown files "
        f"({result.path_links_checked} relative targets, "
        f"{result.fragments_checked} anchors checked)."
    )
    return 0


def main() -> int:
    return run(sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
