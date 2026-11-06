"""A filled PR template must expose a real, lintable Governor Footer."""

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))
spec = importlib.util.spec_from_file_location(
    "check_governor_footer", ROOT / "tools/check_governor_footer.py"
)
assert spec is not None and spec.loader is not None
loaded = importlib.util.module_from_spec(spec)
sys.modules["check_governor_footer"] = loaded
spec.loader.exec_module(loaded)
check_body = loaded.check_body
parse_footer = loaded.parse_footer


def test_filled_template_footer_is_outside_details_and_code_fences():
    root = Path(__file__).resolve().parents[3]
    template = (root / ".github/pull_request_template.md").read_text()
    assert template.index("</details>") < template.index("\n## Governor Footer\n")
    body = template.replace("- trigger: no\n", "- trigger: yes\n")
    body = body.replace(
        "- reviewer: <actual tool or fallback>", "- reviewer: claude-code"
    )
    body = body.replace(": N\n", ": 1\n")
    body = body.replace(
        "- pr-scope-notes: <one-line scope>", "- pr-scope-notes: ticket workflow"
    )
    body = body.replace(
        "- final-verdict: merge-ready/minor-fixes/needs-reinforcement/block",
        "- final-verdict: merge-ready",
    )
    body = body.replace(
        "- links: <PR URL>, n/a", "- links: https://github.com/example/repo/pull/1, n/a"
    )
    fields, violations = parse_footer(body, source="template")
    assert not violations
    assert fields["trigger"][1] == "yes"
    assert not check_body(
        body,
        source="template",
        require_governor_footer=True,
        changed_files=["AGENTS.md"],
    )
    fenced = (
        body.replace("\n## Governor Footer\n", "\n```\n## Governor Footer\n")
        + "\n```\n"
    )
    assert check_body(
        fenced,
        source="fenced",
        require_governor_footer=True,
        changed_files=["AGENTS.md"],
    )


def test_unfilled_template_passes_only_for_non_governor_changes():
    root = Path(__file__).resolve().parents[3]
    template = (root / ".github/pull_request_template.md").read_text()
    assert not check_body(
        template,
        source="template",
        require_governor_footer=True,
        changed_files=["src/user/domain/services/user_service.py"],
    )
    violations = check_body(
        template,
        source="template",
        require_governor_footer=True,
        changed_files=["AGENTS.md"],
    )
    assert [v.reason for v in violations] == [
        "governor-changing PR must declare 'trigger: yes' (ADR 047 D2)"
    ]
