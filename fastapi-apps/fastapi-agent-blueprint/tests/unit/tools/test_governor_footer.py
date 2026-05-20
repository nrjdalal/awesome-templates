"""Tests for tools/check_governor_footer.py (ADR 047 D2)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
TOOL_PATH = REPO_ROOT / "tools" / "check_governor_footer.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("check_governor_footer", TOOL_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_governor_footer"] = module
    spec.loader.exec_module(module)
    return module


cgf = _load_module()


VALID_FOOTER = """\
## Governor Footer
- trigger: yes
- reviewer: codex-cli, claude-code
- rounds: 4
- r-points-fixed: 22
- r-points-deferred: 0
- r-points-rejected: 0
- touched-adr-consequences: ADR047-G3, ADR047-G24
- pr-scope-notes: none
- final-verdict: merge-ready
- links: https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/158
"""


def _wrap_body(
    footer: str,
    *,
    prefix: str = "# PR description\n\nSome prose.\n\n",
    suffix: str = "",
) -> str:
    return prefix + footer + suffix


def test_valid_footer_passes():
    body = _wrap_body(VALID_FOOTER)
    violations = cgf.check_body(
        body, source="t", require_governor_footer=False, changed_files=[]
    )
    assert violations == []


def test_missing_field_fails():
    bad = "\n".join(VALID_FOOTER.splitlines()[:-2] + ["- final-verdict: merge-ready"])
    body = _wrap_body(bad + "\n")
    violations = cgf.check_body(
        body, source="t", require_governor_footer=False, changed_files=[]
    )
    assert any("missing required field 'links'" in v.reason for v in violations)


def test_extra_field_fails():
    bad = VALID_FOOTER.rstrip() + "\n- bonus: 42\n"
    body = _wrap_body(bad)
    violations = cgf.check_body(
        body, source="t", require_governor_footer=False, changed_files=[]
    )
    assert any("unexpected field 'bonus'" in v.reason for v in violations)


def test_wrong_field_order_fails():
    lines = VALID_FOOTER.splitlines()
    # swap trigger and reviewer
    lines[1], lines[2] = lines[2], lines[1]
    body = _wrap_body("\n".join(lines) + "\n")
    violations = cgf.check_body(
        body, source="t", require_governor_footer=False, changed_files=[]
    )
    assert any("out of declared order" in v.reason for v in violations)


def test_malformed_line_fails():
    bad = VALID_FOOTER.replace("- trigger: yes", "-trigger: yes")
    body = _wrap_body(bad)
    violations = cgf.check_body(
        body, source="t", require_governor_footer=False, changed_files=[]
    )
    assert any("- <field>: <value>" in v.reason for v in violations)


def test_double_space_after_colon_fails():
    bad = VALID_FOOTER.replace("- trigger: yes", "- trigger:  yes")
    body = _wrap_body(bad)
    violations = cgf.check_body(
        body, source="t", require_governor_footer=False, changed_files=[]
    )
    assert any("- <field>: <value>" in v.reason for v in violations)


def test_non_canonical_verdict_fails():
    bad = VALID_FOOTER.replace("merge-ready", "ready-to-merge")
    body = _wrap_body(bad)
    violations = cgf.check_body(
        body, source="t", require_governor_footer=False, changed_files=[]
    )
    assert any("final-verdict must be one of" in v.reason for v in violations)


def test_non_canonical_trigger_fails():
    bad = VALID_FOOTER.replace("- trigger: yes", "- trigger: maybe")
    body = _wrap_body(bad)
    violations = cgf.check_body(
        body, source="t", require_governor_footer=False, changed_files=[]
    )
    assert any("trigger must be 'yes' or 'no'" in v.reason for v in violations)


def test_non_integer_rounds_fails():
    bad = VALID_FOOTER.replace("- rounds: 4", "- rounds: four")
    body = _wrap_body(bad)
    violations = cgf.check_body(
        body, source="t", require_governor_footer=False, changed_files=[]
    )
    assert any("rounds must be a non-negative integer" in v.reason for v in violations)


def test_rounds_zero_with_trigger_yes_fails():
    bad = VALID_FOOTER.replace("- rounds: 4", "- rounds: 0")
    body = _wrap_body(bad)
    violations = cgf.check_body(
        body, source="t", require_governor_footer=False, changed_files=[]
    )
    assert any("rounds must be >= 1 when trigger: yes" in v.reason for v in violations)


def test_rounds_zero_allowed_when_trigger_no():
    bad = VALID_FOOTER.replace("- trigger: yes", "- trigger: no").replace(
        "- rounds: 4", "- rounds: 0"
    )
    body = _wrap_body(bad)
    violations = cgf.check_body(
        body, source="t", require_governor_footer=False, changed_files=[]
    )
    assert all("rounds must be >= 1" not in v.reason for v in violations)


def test_invalid_adr_id_fails():
    bad = VALID_FOOTER.replace("ADR047-G3, ADR047-G24", "ADR47-G3")
    body = _wrap_body(bad)
    violations = cgf.check_body(
        body, source="t", require_governor_footer=False, changed_files=[]
    )
    assert any("ADR\\d{3}-G\\d+" in v.reason for v in violations)


def test_touched_adr_none_passes():
    bad = VALID_FOOTER.replace("ADR047-G3, ADR047-G24", "none")
    body = _wrap_body(bad)
    violations = cgf.check_body(
        body, source="t", require_governor_footer=False, changed_files=[]
    )
    assert violations == []


def test_invalid_links_fails():
    bad = VALID_FOOTER.replace(
        "https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/158",
        "not-a-url",
    )
    body = _wrap_body(bad)
    violations = cgf.check_body(
        body, source="t", require_governor_footer=False, changed_files=[]
    )
    assert any("http(s) URL or 'n/a'" in v.reason for v in violations)


def test_links_na_passes():
    bad = VALID_FOOTER.replace(
        "https://github.com/Mr-DooSun/fastapi-agent-blueprint/pull/158",
        "n/a",
    )
    body = _wrap_body(bad)
    violations = cgf.check_body(
        body, source="t", require_governor_footer=False, changed_files=[]
    )
    assert violations == []


def test_omitted_footer_passes_without_require_flag():
    body = "# PR description\n\nNo footer here.\n"
    violations = cgf.check_body(
        body, source="t", require_governor_footer=False, changed_files=[]
    )
    assert violations == []


def test_fenced_footer_only_does_not_parse():
    """A `## Governor Footer` heading inside a fenced code block must not be parsed.

    ADR 047 and the PR template both contain fenced footer examples; the linter
    must not treat them as the real footer.
    """

    body = "# PR description\n\n```\n## Governor Footer\n- trigger: yes\n```\n\nNo real footer above.\n"
    violations = cgf.check_body(
        body, source="t", require_governor_footer=False, changed_files=[]
    )
    assert violations == []


def test_fenced_example_plus_real_footer_parses_real_one():
    body = (
        "# PR description\n\n"
        "```\n## Governor Footer\n- trigger: yes\n- broken: shape\n```\n\n"
        "Real footer follows:\n\n" + VALID_FOOTER
    )
    violations = cgf.check_body(
        body, source="t", require_governor_footer=False, changed_files=[]
    )
    assert violations == []


def test_governor_changing_with_missing_footer_fails_in_require_mode():
    body = "# PR description\n\nNo footer.\n"
    violations = cgf.check_body(
        body,
        source="t",
        require_governor_footer=True,
        changed_files=["AGENTS.md"],
    )
    assert any("missing the '## Governor Footer' block" in v.reason for v in violations)


def test_governor_changing_with_trigger_no_fails_in_require_mode():
    bad = VALID_FOOTER.replace("- trigger: yes", "- trigger: no").replace(
        "- rounds: 4", "- rounds: 0"
    )
    body = _wrap_body(bad)
    violations = cgf.check_body(
        body,
        source="t",
        require_governor_footer=True,
        changed_files=["AGENTS.md"],
    )
    assert any("must declare 'trigger: yes'" in v.reason for v in violations)


def test_non_governor_changing_with_missing_footer_passes_in_require_mode():
    body = "# PR description\n\nNo footer.\n"
    violations = cgf.check_body(
        body,
        source="t",
        require_governor_footer=True,
        changed_files=["src/user/domain/services/user_service.py"],
    )
    assert violations == []


def test_non_governor_changing_with_trigger_no_passes_in_require_mode():
    bad = VALID_FOOTER.replace("- trigger: yes", "- trigger: no").replace(
        "- rounds: 4", "- rounds: 0"
    )
    body = _wrap_body(bad)
    violations = cgf.check_body(
        body,
        source="t",
        require_governor_footer=True,
        changed_files=["src/user/domain/services/user_service.py"],
    )
    assert violations == []


def test_log_only_backfill_is_not_governor_changing():
    body = "# PR description\n\nNo footer.\n"
    violations = cgf.check_body(
        body,
        source="t",
        require_governor_footer=True,
        changed_files=["docs/history/archive/governor-review-log/pr-125-foo.md"],
    )
    assert violations == []


def test_bypass_token_skips_non_governor_pr():
    body = "# PR description\n\n[skip-governor-footer]\n\nMalformed footer below.\n\n## Governor Footer\n- trigger: maybe\n"
    violations = cgf.check_body(
        body,
        source="t",
        require_governor_footer=True,
        changed_files=["src/user/service.py"],
    )
    assert violations == []


def test_bypass_token_blocked_for_governor_pr():
    body = "# PR description\n\n[skip-governor-footer]\n"
    violations = cgf.check_body(
        body,
        source="t",
        require_governor_footer=True,
        changed_files=["AGENTS.md"],
    )
    assert len(violations) == 1
    assert "[skip-governor-footer]" in violations[0].reason
    assert "ADR 048-G1" in violations[0].reason


def test_bypass_token_in_non_ci_mode_allows_governor_file():
    # Without --require-governor-footer, is_governor is always False,
    # so the escape token still works for local dry-runs (ADR 048 D3).
    body = "# PR description\n\n[skip-governor-footer]\n"
    violations = cgf.check_body(
        body,
        source="t",
        require_governor_footer=False,
        changed_files=["AGENTS.md"],
    )
    assert violations == []


def test_bypass_token_in_code_span_does_not_trigger():
    # Mentioning `[skip-governor-footer]` inside inline code or a fenced block
    # in the PR description (e.g. documentation) must not activate the bypass.
    body = (
        "## Changes\n\n"
        "- `tools/check_governor_footer.py`: `[skip-governor-footer]` → hard Violation\n\n"
        "```\n"
        "example: [skip-governor-footer]\n"
        "```\n\n"
        "## Governor Footer\n"
        "- trigger: yes\n"
        "- reviewer: codex-cli\n"
        "- rounds: 1\n"
        "- r-points-fixed: 0\n"
        "- r-points-deferred: 0\n"
        "- r-points-rejected: 0\n"
        "- touched-adr-consequences: none\n"
        "- pr-scope-notes: none\n"
        "- final-verdict: merge-ready\n"
        "- links: n/a\n"
    )
    violations = cgf.check_body(
        body,
        source="t",
        require_governor_footer=True,
        changed_files=["AGENTS.md"],
    )
    assert violations == [], violations


def test_changed_files_at_file_form(tmp_path: Path):
    list_file = tmp_path / "files.txt"
    list_file.write_text("AGENTS.md\nsrc/user/foo.py\n", encoding="utf-8")
    files = cgf._load_changed_files(f"@{list_file}")
    assert files == ["AGENTS.md", "src/user/foo.py"]


def test_changed_files_inline_form():
    files = cgf._load_changed_files(
        "AGENTS.md, src/user/foo.py , .github/workflows/ci.yml"
    )
    assert files == ["AGENTS.md", "src/user/foo.py", ".github/workflows/ci.yml"]


def test_main_file_mode(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    body_file = tmp_path / "body.md"
    body_file.write_text(_wrap_body(VALID_FOOTER), encoding="utf-8")
    rc = cgf.main([str(body_file)])
    captured = capsys.readouterr()
    assert rc == 0
    assert "0 violations" in captured.out


def test_main_stdin_mode(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    import io

    monkeypatch.setattr(sys, "stdin", io.StringIO(_wrap_body(VALID_FOOTER)))
    rc = cgf.main(["-"])
    captured = capsys.readouterr()
    assert rc == 0
    assert "0 violations" in captured.out


def test_main_failure_exit_code(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    body_file = tmp_path / "body.md"
    bad = VALID_FOOTER.replace("- trigger: yes", "- trigger: maybe")
    body_file.write_text(_wrap_body(bad), encoding="utf-8")
    rc = cgf.main([str(body_file)])
    captured = capsys.readouterr()
    assert rc == 1
    assert "violations" in captured.out
