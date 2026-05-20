"""Governor Footer block checker (ADR 047 D2).

Validates the ``## Governor Footer`` block carried in PR description bodies for
governor-changing PRs (per ``docs/ai/shared/governor-paths.md`` Tier A / B / C
globs minus exclusions). Replaces the per-PR ``governor-review-log/`` archive
artefact and ``tools/check_g_closure.py`` enforcement after ADR 047.

V1 validates block shape only:

- Single ``## Governor Footer`` heading at top of section, terminated by next
  ``^## `` heading or EOF. Headings inside Markdown fenced code blocks
  (``` ``` ``` or ``~~~``) are skipped.
- Each non-blank line in the block matches ``- <field>: <value>`` with single
  spaces.
- All 10 fields present, in declared order, no extras, no duplicates.
- Enum vocabularies for ``trigger`` and ``final-verdict`` match exactly.
- Integer fields parse as non-negative ints; ``rounds: 0`` is rejected when
  ``trigger: yes``.
- ``touched-adr-consequences`` entries match ``ADR\\d{3}-G\\d+`` or are the
  literal ``none``.
- ``links`` accepts URLs or the literal ``n/a``.

Does NOT validate: that touched-adr-consequences IDs actually exist in any
ADR (semantic check); round count consistency with R-points totals.

``reviewer`` field is intentionally open-vocabulary by design (ADR 047 D2 /
ADR 048 D3). The linter accepts any non-blank string. The three documented
modes are a tool name (e.g. ``codex-cli``, ``claude-code``), ``self-structured``
(single-tool structured checklist per ADR 048 D4), or
``human:<github-handle>``. Multiple modes may be comma-separated. This
open-vocabulary design was present from the initial implementation;
ADR 048 D3 formally documents the accepted vocabulary without changing
the linter code.

Used by:
- ``.github/workflows/governor-footer-lint.yml`` CI workflow.
- ``tests/unit/tools/test_governor_footer.py``.
- Ad-hoc local dry-run: ``python3 tools/check_governor_footer.py <body.md>``.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

HEADING = "## Governor Footer"
FENCED_CODE_RE = re.compile(r"^[ ]{0,3}(```|~~~)")
HEADING_RE = re.compile(r"^##\s")
BYPASS_TOKEN = "[skip-governor-footer]"  # noqa: S105 — opt-in escape token, not a credential
_FENCED_BLOCK_RE = re.compile(r"```.*?```|~~~.*?~~~", re.DOTALL)
_CODE_SPAN_RE = re.compile(r"`[^`\n]+`")


def _body_without_code(body: str) -> str:
    """Strip fenced code blocks and inline code spans for bypass-token detection."""
    without_fenced = _FENCED_BLOCK_RE.sub("", body)
    return _CODE_SPAN_RE.sub("", without_fenced)


FIELD_ORDER = (
    "trigger",
    "reviewer",
    "rounds",
    "r-points-fixed",
    "r-points-deferred",
    "r-points-rejected",
    "touched-adr-consequences",
    "pr-scope-notes",
    "final-verdict",
    "links",
)
TRIGGER_VALUES = frozenset({"yes", "no"})
VERDICT_VALUES = frozenset(
    {"merge-ready", "minor-fixes", "needs-reinforcement", "block"}
)
INTEGER_FIELDS = frozenset(
    {"rounds", "r-points-fixed", "r-points-deferred", "r-points-rejected"}
)
LINE_RE = re.compile(r"^- ([a-z][a-z0-9-]*): (\S.*)$")
ADR_ID_RE = re.compile(r"^ADR\d{3}-G\d+$")
URL_RE = re.compile(r"^https?://\S+$")


@dataclass(frozen=True)
class Violation:
    source: str
    line_number: int
    reason: str
    line_content: str = ""

    def format(self) -> str:
        suffix = f"\n  {self.line_content!r}" if self.line_content else ""
        return f"{self.source}:{self.line_number}: {self.reason}{suffix}"


def _strip_fenced_blocks(lines: list[str]) -> list[tuple[int, str]]:
    """Return ``(line_number, content)`` pairs with fenced code lines removed.

    Line numbers are 1-based and preserved from the original input so violation
    messages cite the source position.
    """

    out: list[tuple[int, str]] = []
    in_fence = False
    for idx, raw in enumerate(lines, start=1):
        if FENCED_CODE_RE.match(raw):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        out.append((idx, raw))
    return out


def _find_footer_block(
    stripped: list[tuple[int, str]],
) -> tuple[int, list[tuple[int, str]]] | None:
    """Locate the Governor Footer heading and the lines until the next ``##`` heading.

    Returns the ``(heading_line_number, body_lines)`` tuple, or ``None`` if no
    real (non-fenced) heading is found.
    """

    heading_idx = None
    for i, (_lineno, line) in enumerate(stripped):
        if line.strip() == HEADING:
            heading_idx = i
            break
    if heading_idx is None:
        return None

    body: list[tuple[int, str]] = []
    for entry_lineno, line in stripped[heading_idx + 1 :]:
        if HEADING_RE.match(line):
            break
        body.append((entry_lineno, line))
    return stripped[heading_idx][0], body


def _validate_value(
    field: str, value: str, lineno: int, source: str
) -> list[Violation]:
    violations: list[Violation] = []
    if field == "trigger":
        if value not in TRIGGER_VALUES:
            violations.append(
                Violation(
                    source, lineno, f"trigger must be 'yes' or 'no', got {value!r}"
                )
            )
    elif field == "final-verdict":
        if value not in VERDICT_VALUES:
            violations.append(
                Violation(
                    source,
                    lineno,
                    f"final-verdict must be one of {sorted(VERDICT_VALUES)}, got {value!r}",
                )
            )
    elif field in INTEGER_FIELDS:
        if not value.isdigit():
            violations.append(
                Violation(
                    source,
                    lineno,
                    f"{field} must be a non-negative integer, got {value!r}",
                )
            )
    elif field == "touched-adr-consequences":
        if value != "none":
            entries = [v.strip() for v in value.split(",")]
            for entry in entries:
                if not ADR_ID_RE.match(entry):
                    violations.append(
                        Violation(
                            source,
                            lineno,
                            f"touched-adr-consequences entry must match ADR\\d{{3}}-G\\d+ or 'none', got {entry!r}",
                        )
                    )
    elif field == "links":
        if value != "n/a":
            entries = [v.strip() for v in value.split(",")]
            for entry in entries:
                if not URL_RE.match(entry):
                    violations.append(
                        Violation(
                            source,
                            lineno,
                            f"links entry must be an http(s) URL or 'n/a', got {entry!r}",
                        )
                    )
    return violations


def parse_footer(
    body: str, source: str = "<input>"
) -> tuple[dict[str, tuple[int, str]] | None, list[Violation]]:
    """Parse a Governor Footer block out of a markdown body.

    Returns ``(fields_or_none, violations)``. ``fields_or_none`` is ``None``
    when no Governor Footer heading exists outside fenced code; it is a dict
    mapping ``field_name -> (line_number, value)`` otherwise. Shape, ordering,
    and value-grammar violations populate ``violations``.
    """

    if BYPASS_TOKEN in _body_without_code(body):
        return None, []

    raw_lines = body.splitlines()
    stripped = _strip_fenced_blocks(raw_lines)
    located = _find_footer_block(stripped)
    if located is None:
        return None, []

    heading_line, body_lines = located
    fields: dict[str, tuple[int, str]] = {}
    seen_order: list[str] = []
    violations: list[Violation] = []

    for lineno, line in body_lines:
        if not line.strip():
            continue
        m = LINE_RE.match(line)
        if not m:
            violations.append(
                Violation(
                    source,
                    lineno,
                    "expected '- <field>: <value>' (single space after '-' and ':')",
                    line,
                )
            )
            continue
        field, value = m.group(1), m.group(2)
        if field in fields:
            violations.append(Violation(source, lineno, f"duplicate field {field!r}"))
            continue
        fields[field] = (lineno, value)
        seen_order.append(field)
        violations.extend(_validate_value(field, value, lineno, source))

    expected = list(FIELD_ORDER)
    missing = [f for f in expected if f not in fields]
    extra = [f for f in seen_order if f not in expected]
    for f in missing:
        violations.append(
            Violation(source, heading_line, f"missing required field {f!r}")
        )
    for f in extra:
        lineno, _ = fields[f]
        violations.append(
            Violation(source, lineno, f"unexpected field {f!r} not in declared schema")
        )

    common = [f for f in seen_order if f in expected]
    expected_filtered = [f for f in expected if f in fields]
    if common != expected_filtered:
        first_misordered = next(
            (
                i
                for i, f in enumerate(common)
                if i >= len(expected_filtered) or f != expected_filtered[i]
            ),
            None,
        )
        if first_misordered is not None and first_misordered < len(common):
            f = common[first_misordered]
            lineno, _ = fields[f]
            violations.append(
                Violation(
                    source,
                    lineno,
                    f"field {f!r} is out of declared order (expected {expected_filtered[first_misordered]!r})",
                )
            )

    if "rounds" in fields and fields.get("trigger", (0, ""))[1] == "yes":
        rounds_lineno, rounds_value = fields["rounds"]
        if rounds_value.isdigit() and int(rounds_value) == 0:
            violations.append(
                Violation(
                    source,
                    rounds_lineno,
                    "rounds must be >= 1 when trigger: yes (independent review must run at least once)",
                )
            )

    return fields, violations


def _load_changed_files(arg: str | None) -> list[str]:
    if not arg:
        return []
    if arg.startswith("@"):
        path = Path(arg[1:])
        text = path.read_text(encoding="utf-8")
        return [line.strip() for line in text.splitlines() if line.strip()]
    return [item.strip() for item in arg.split(",") if item.strip()]


def _is_governor_changing(changed_files: list[str]) -> bool:
    """Reuse the shared governor module for trigger detection."""

    sys.path.insert(0, str(REPO_ROOT / ".agents" / "shared"))
    try:
        from governor.completion_gate import (  # type: ignore[import-not-found]
            is_governor_changing,
            is_log_only_backfill,
            parse_trigger_globs,
        )
        from governor.paths import GOVERNOR_PATHS_MD  # type: ignore[import-not-found]
    finally:
        sys.path.pop(0)
    if not changed_files:
        return False
    if is_log_only_backfill(changed_files):
        return False
    globs = parse_trigger_globs(GOVERNOR_PATHS_MD)
    return is_governor_changing(changed_files, globs)


def check_body(
    body: str,
    *,
    source: str,
    require_governor_footer: bool,
    changed_files: list[str],
) -> list[Violation]:
    if require_governor_footer:
        is_governor = _is_governor_changing(changed_files)
    else:
        is_governor = False

    if BYPASS_TOKEN in _body_without_code(body):
        if is_governor:
            # Governor-changing PRs cannot bypass mandatory independent review (ADR 048-G1).
            # Use docs/ai/shared/governor-paths.md § Exclusions for path-level exemptions.
            return [
                Violation(
                    source,
                    0,
                    f"'{BYPASS_TOKEN}' cannot be used in governor-changing PRs (ADR 048-G1:"
                    " independent review is mandatory). Add a valid '## Governor Footer' block."
                    " To exempt a specific path pattern, add it to"
                    " docs/ai/shared/governor-paths.md § Exclusions instead.",
                )
            ]
        return []

    fields, violations = parse_footer(body, source=source)

    if require_governor_footer and is_governor:
        if fields is None:
            violations.append(
                Violation(
                    source,
                    0,
                    "governor-changing PR is missing the '## Governor Footer' block (ADR 047 D2)."
                    " See .github/pull_request_template.md for the format."
                    " reviewer accepts: a tool name (cross-tool), 'self-structured' (single-tool env),"
                    " or 'human:<handle>'.",
                )
            )
        else:
            trigger_entry = fields.get("trigger")
            if trigger_entry is None:
                pass
            elif trigger_entry[1] != "yes":
                violations.append(
                    Violation(
                        source,
                        trigger_entry[0],
                        "governor-changing PR must declare 'trigger: yes' (ADR 047 D2)",
                    )
                )

    return violations


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate Governor Footer block (ADR 047 D2)."
    )
    parser.add_argument(
        "body",
        nargs="?",
        default="-",
        help="Path to markdown body file, or '-' to read from stdin (default).",
    )
    parser.add_argument(
        "--require-governor-footer",
        action="store_true",
        help="Treat missing/disabled footer on a governor-changing PR as a hard failure (CI mode).",
    )
    parser.add_argument(
        "--changed-files",
        default=None,
        help="Comma-separated path list, or '@<file>' to read newline-separated paths.",
    )
    args = parser.parse_args(argv)

    if args.body == "-":
        body = sys.stdin.read()
        source = "<stdin>"
    else:
        path = Path(args.body)
        body = path.read_text(encoding="utf-8")
        source = str(path)

    changed_files = _load_changed_files(args.changed_files)
    violations = check_body(
        body,
        source=source,
        require_governor_footer=args.require_governor_footer,
        changed_files=changed_files,
    )

    if not violations:
        print("Governor Footer: 0 violations.")
        return 0

    print(f"Governor Footer violations ({len(violations)}):")
    for v in violations:
        print(v.format())
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
