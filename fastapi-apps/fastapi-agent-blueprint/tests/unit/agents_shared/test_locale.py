"""Tests for ``governor.locale`` and AGENT_LOCALE-resolved hook emission (#133).

Coverage layers (verified through 8 rounds of Codex cross-validation, v8):

1. Direct API — get_locale_string() for default / explicit / unknown / case
   / whitespace / missing-key locales.
2. Identity / schema — _LOCALE_EN re-exports verify.REMINDER_TEXT and
   completion_gate.GOVERNOR_REMINDER_* by reference (drift impossible).
3. Per-hook emission map — every emitter Hook uses only the keys defined
   for its surface (Claude shell: 8, Codex Stop: 10).
4. Drift guards — locale.py _LOCALE_EN values appear as substrings in
   the hook source files (file-position-agnostic, line-agnostic).
5. AST / tokenize guard — locale.py only contains Hangul inside
   _LOCALE_KO mapping values. Comments, docstrings, identifiers,
   _LOCALE_EN values must remain ASCII.
6. Cycle import guard — verify.py / completion_gate.py do not import
   from .locale.
7. CLI mode — python -m governor.locale KEY works (-m only; direct path
   execution unsupported).
8. Always-fallback callsite guard (IC-19) — every hook callsite of
   _resolve_locale_string("KEY") is combined with `or KEY`; every _loc()
   call has 2 positional args with non-empty string fallback.
9. In-process emission — verify-first / completion-gate / Codex
   build_segments emit the right locale-resolved text without subprocess
   flakiness.
10. Shell subprocess in temp git repo — Bash hook emits ko/en correctly.
"""

from __future__ import annotations

import ast
import io
import os
import re
import subprocess
import sys
import tokenize
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SHARED_DIR = REPO_ROOT / ".agents" / "shared"

# Only the shared governor package goes on sys.path here. We deliberately
# do NOT push `.claude/hooks` or `.codex/hooks` — doing so leaks search-order
# ambiguity into tests/unit/agents_shared/test_completion_gate.py, which
# imports both Claude and Codex completion_gate via spec_from_file_location
# and depends on sys.path being clean for the `from verify_first import
# session_id` resolution inside Codex completion_gate.py. All hook module
# loads in THIS file use spec_from_file_location with explicit pre-load of
# Codex verify_first under the canonical name (see _load_codex_completion_gate).
if str(SHARED_DIR) not in sys.path:
    sys.path.insert(0, str(SHARED_DIR))

from governor import (  # noqa: E402
    GOVERNOR_REMINDER_NO_PR,
    GOVERNOR_REMINDER_WITH_PR,
    REMINDER_TEXT,
)
from governor import locale as locale_mod  # noqa: E402

HANGUL_RE = re.compile(r"[가-힯ᄀ-ᇿ㄰-㆏]")


_EXPECTED_KEYS = frozenset(
    {
        # 3 reminder constants
        "REMINDER_TEXT",
        "GOVERNOR_REMINDER_WITH_PR",
        "GOVERNOR_REMINDER_NO_PR",
        # 15 sync advisory keys (8 shell + 7 codex-only + 2 shared = 15 distinct)
        "SYNC_STRONG_HEADER",
        "SYNC_STRONG_FOOTER",
        "SYNC_NORM_HEADER",
        "SYNC_NORM_FOOTER",
        "SYNC_FOUNDATION_FILES_HEADER",
        "SYNC_STRUCTURE_FILES_HEADER",
        "SYNC_CLAUDE_RUN",
        "SYNC_CODEX_RUN_ALSO",
        "SYNC_CODEX_RUN_PRIMARY",
        "SYNC_CLAUDE_RUN_ALSO",
        "SYNC_INCOMPLETE_NOTE",
        "SYNC_REVIEW_TARGETS_NOTE",
        "SYNC_REPORT_BOTH_NOTE",
        "SYNC_FOUNDATION_LEAD",
        "SYNC_STRUCTURE_LEAD",
    }
)


# ---------------------------------------------------------------------------
# 1. Direct API
# ---------------------------------------------------------------------------
def test_default_locale_is_english(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AGENT_LOCALE", raising=False)
    assert locale_mod.get_locale_string("REMINDER_TEXT") == REMINDER_TEXT


def test_explicit_en_locale(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_LOCALE", "en")
    assert locale_mod.get_locale_string("REMINDER_TEXT") == REMINDER_TEXT


def test_ko_locale_reminder_text_structure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_LOCALE", "ko")
    text = locale_mod.get_locale_string("REMINDER_TEXT")
    assert text != REMINDER_TEXT  # actually translated
    lines = text.split("\n")
    assert len(lines) == 4
    assert lines[0].startswith("[verify-first] ")  # English tag preserved
    assert "Suggested next" in lines[2]  # technical anchor preserved
    assert "[exploration]" in lines[3] and "[탐색]" in lines[3]


def test_ko_locale_completion_gate_no_pr(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_LOCALE", "ko")
    text = locale_mod.get_locale_string("GOVERNOR_REMINDER_NO_PR")
    assert text != GOVERNOR_REMINDER_NO_PR
    assert "[completion-gate]" in text
    assert "PR" in text


def test_ko_locale_with_pr_placeholder_preserved(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AGENT_LOCALE", "ko")
    template = locale_mod.get_locale_string("GOVERNOR_REMINDER_WITH_PR")
    assert "{pr}" in template
    rendered = template.format(pr=999)
    assert "999" in rendered
    assert "{pr}" not in rendered


def test_unknown_locale_falls_back_to_english(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AGENT_LOCALE", "fr")
    assert locale_mod.get_locale_string("REMINDER_TEXT") == REMINDER_TEXT


def test_uppercase_locale_is_normalized(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_LOCALE", "KO")
    text = locale_mod.get_locale_string("REMINDER_TEXT")
    assert text != REMINDER_TEXT  # ko table picked


def test_empty_locale_falls_back_to_english(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_LOCALE", "")
    assert locale_mod.get_locale_string("REMINDER_TEXT") == REMINDER_TEXT


def test_whitespace_locale_is_stripped(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_LOCALE", "  ko  ")
    text = locale_mod.get_locale_string("REMINDER_TEXT")
    assert text != REMINDER_TEXT


def test_missing_key_in_partial_locale_falls_back_per_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If _LOCALE_KO loses a key, the resolver returns English (no KeyError)."""
    monkeypatch.setenv("AGENT_LOCALE", "ko")
    patched = dict(locale_mod._LOCALE_KO)
    patched.pop("REMINDER_TEXT", None)
    monkeypatch.setattr(
        locale_mod, "_LOCALES", {"en": locale_mod._LOCALE_EN, "ko": patched}
    )
    assert locale_mod.get_locale_string("REMINDER_TEXT") == REMINDER_TEXT


def test_unknown_key_returns_empty_string(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AGENT_LOCALE", raising=False)
    assert locale_mod.get_locale_string("DOES_NOT_EXIST") == ""


# ---------------------------------------------------------------------------
# 2. Identity / schema (drift impossible by construction)
# ---------------------------------------------------------------------------
def test_locale_en_uses_canonical_constants_by_reference() -> None:
    """The English table re-exports verify/completion_gate constants — same
    object, not a literal copy. A future divergence in the canonical
    constant is reflected automatically."""
    assert locale_mod._LOCALE_EN["REMINDER_TEXT"] is REMINDER_TEXT
    assert (
        locale_mod._LOCALE_EN["GOVERNOR_REMINDER_WITH_PR"] is GOVERNOR_REMINDER_WITH_PR
    )
    assert locale_mod._LOCALE_EN["GOVERNOR_REMINDER_NO_PR"] is GOVERNOR_REMINDER_NO_PR


def test_locale_ko_keys_subset_of_en() -> None:
    """Every key in _LOCALE_KO must exist in _LOCALE_EN. No ko-only keys."""
    extra = set(locale_mod._LOCALE_KO) - set(locale_mod._LOCALE_EN)
    assert not extra, f"_LOCALE_KO has keys missing from _LOCALE_EN: {extra}"


def test_locale_keys_match_expected_inventory() -> None:
    """The 18-key inventory is pinned. Adding a key requires updating
    _EXPECTED_KEYS in this test (forces awareness)."""
    assert set(locale_mod._LOCALE_EN) == _EXPECTED_KEYS


# ---------------------------------------------------------------------------
# 3. Korean preserves command tokens
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "key,must_contain",
    [
        ("SYNC_STRONG_HEADER", "/sync-guidelines"),
        ("SYNC_NORM_HEADER", "/sync-guidelines"),
        ("SYNC_CLAUDE_RUN", "/sync-guidelines"),
        ("SYNC_CODEX_RUN_ALSO", "$sync-guidelines"),
        ("SYNC_CODEX_RUN_PRIMARY", "$sync-guidelines"),
        ("SYNC_CLAUDE_RUN_ALSO", "/sync-guidelines"),
        ("SYNC_FOUNDATION_FILES_HEADER", "Foundation"),
        ("SYNC_INCOMPLETE_NOTE", "AUTO-FIX"),
        ("SYNC_INCOMPLETE_NOTE", "REVIEW"),
        ("SYNC_INCOMPLETE_NOTE", "project-dna"),
        ("SYNC_REPORT_BOTH_NOTE", "AUTO-FIX"),
        ("SYNC_REPORT_BOTH_NOTE", "REVIEW"),
    ],
)
def test_ko_preserves_command_tokens(
    monkeypatch: pytest.MonkeyPatch, key: str, must_contain: str
) -> None:
    monkeypatch.setenv("AGENT_LOCALE", "ko")
    text = locale_mod.get_locale_string(key)
    assert must_contain in text, f"ko[{key}] missing token {must_contain!r}: {text!r}"


# ---------------------------------------------------------------------------
# 4. Language-policy checker exemption
# ---------------------------------------------------------------------------
def test_locale_py_passes_language_policy_checker() -> None:
    """find_violations() returns [] for the locale data file via
    LOCALE_DATA_FILES file-wide skip."""
    sys.path.insert(0, str(REPO_ROOT / "tools"))
    import check_language_policy as clp  # noqa: PLC0415

    locale_path = SHARED_DIR / "governor" / "locale.py"
    assert clp.find_violations(locale_path, repo_root=REPO_ROOT) == []


def test_pre_commit_argv_mode_locale_py_passes() -> None:
    """The checker invoked with explicit file argv (= how pre-commit calls
    it) returns 0 for locale.py — file-wide skip works in argv mode too."""
    result = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "tools" / "check_language_policy.py"),
            ".agents/shared/governor/locale.py",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"checker failed in argv mode for locale.py:\nstdout={result.stdout}\nstderr={result.stderr}"
    )


def test_locale_exception_documented_consistently() -> None:
    """No active policy/harness/skill file may carry the stale 'only/sole
    exception' phrasing about bilingual tokens after the LOCALE_DATA_FILES
    carve-out lands. Historical governor-review-log/ entries quote past
    policy state and are excluded by allowlist."""
    in_scope = [
        "AGENTS.md",
        "CLAUDE.md",
        ".claude/rules/project-status.md",
        "docs/ai/shared/skills/sync-guidelines.md",
        "docs/ai/shared/skills/review-pr.md",
        "docs/ai/shared/skills/review-architecture.md",
        "docs/ai/shared/skills/security-review.md",
        "docs/ai/shared/drift-checklist.md",
        "tools/check_language_policy.py",
        ".pre-commit-config.yaml",
    ]
    patterns = [
        re.compile(r"bilingual.{0,120}(only|sole)\s+exception\b", re.I | re.S),
        re.compile(r"(only|sole)\s+exception\b.{0,120}bilingual", re.I | re.S),
        re.compile(
            r"\bthe\s+only\s+(Korean|Hangul)\s+strings?\s+(allowed|permitted)",
            re.I,
        ),
    ]
    matches: list[str] = []
    for rel in in_scope:
        text = (REPO_ROOT / rel).read_text(encoding="utf-8")
        for pat in patterns:
            for m in pat.finditer(text):
                line = text[: m.start()].count("\n") + 1
                matches.append(f"{rel}:{line}: {m.group(0)[:80]!r}")
    assert not matches, "stale 'only/sole exception' phrasing remains: " + "; ".join(
        matches
    )


# ---------------------------------------------------------------------------
# 5. Per-hook emission map
# ---------------------------------------------------------------------------
def _extract_locale_keys_from_python(path: Path) -> set[str]:
    """Return the set of locale keys passed as the first arg of
    _resolve_locale_string(...) or _loc(...) calls."""
    src = path.read_text(encoding="utf-8")
    tree = ast.parse(src)
    keys: set[str] = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in {"_resolve_locale_string", "_loc"}
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ):
            keys.add(node.args[0].value)
    return keys


def _extract_locale_keys_from_shell(path: Path) -> set[str]:
    """Return the set of locale keys passed as the first arg of
    _resolve_locale calls in a Bash file."""
    text = path.read_text(encoding="utf-8")
    return set(re.findall(r"_resolve_locale\s+(\w+)", text))


def test_claude_verify_first_emission_keys() -> None:
    keys = _extract_locale_keys_from_python(
        REPO_ROOT / ".claude" / "hooks" / "verify_first.py"
    )
    assert keys == {"REMINDER_TEXT"}


def test_claude_completion_gate_emission_keys() -> None:
    keys = _extract_locale_keys_from_python(
        REPO_ROOT / ".claude" / "hooks" / "completion_gate.py"
    )
    assert keys == {"GOVERNOR_REMINDER_WITH_PR", "GOVERNOR_REMINDER_NO_PR"}


def test_codex_completion_gate_emission_keys() -> None:
    keys = _extract_locale_keys_from_python(
        REPO_ROOT / ".codex" / "hooks" / "completion_gate.py"
    )
    assert keys == {"GOVERNOR_REMINDER_WITH_PR", "GOVERNOR_REMINDER_NO_PR"}


def test_codex_verify_first_emission_keys_via_helper() -> None:
    """verify_first.localized_reminder_text() is the only place that
    resolves REMINDER_TEXT on the Codex side. The Stop hook calls this
    helper instead of touching the resolver directly, so the helper's
    callsite is the only resolver entry."""
    keys = _extract_locale_keys_from_python(
        REPO_ROOT / ".codex" / "hooks" / "verify_first.py"
    )
    assert keys == {"REMINDER_TEXT"}


def test_codex_stop_sync_emission_keys() -> None:
    keys = _extract_locale_keys_from_python(
        REPO_ROOT / ".codex" / "hooks" / "stop-sync-reminder.py"
    )
    expected = {
        "SYNC_FOUNDATION_LEAD",
        "SYNC_FOUNDATION_FILES_HEADER",
        "SYNC_CODEX_RUN_PRIMARY",
        "SYNC_CLAUDE_RUN_ALSO",
        "SYNC_INCOMPLETE_NOTE",
        "SYNC_REVIEW_TARGETS_NOTE",
        "SYNC_STRUCTURE_LEAD",
        "SYNC_STRUCTURE_FILES_HEADER",
        "SYNC_REPORT_BOTH_NOTE",
    }
    assert keys == expected


def test_claude_shell_emission_keys() -> None:
    keys = _extract_locale_keys_from_shell(
        REPO_ROOT / ".claude" / "hooks" / "stop-sync-reminder.sh"
    )
    expected = {
        "SYNC_STRONG_HEADER",
        "SYNC_STRONG_FOOTER",
        "SYNC_NORM_HEADER",
        "SYNC_NORM_FOOTER",
        "SYNC_FOUNDATION_FILES_HEADER",
        "SYNC_STRUCTURE_FILES_HEADER",
        "SYNC_CLAUDE_RUN",
        "SYNC_CODEX_RUN_ALSO",
    }
    assert keys == expected


# ---------------------------------------------------------------------------
# 6. Drift guards — _LOCALE_EN[KEY] must appear as substring in each emitter
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "key",
    [
        "SYNC_STRONG_HEADER",
        "SYNC_STRONG_FOOTER",
        "SYNC_NORM_HEADER",
        "SYNC_NORM_FOOTER",
        "SYNC_FOUNDATION_FILES_HEADER",
        "SYNC_STRUCTURE_FILES_HEADER",
        "SYNC_CLAUDE_RUN",
        "SYNC_CODEX_RUN_ALSO",
    ],
)
def test_shell_fallback_string_matches_locale_en(key: str) -> None:
    """Bash uses single-line single-quoted fallbacks — substring match works."""
    text = (REPO_ROOT / ".claude" / "hooks" / "stop-sync-reminder.sh").read_text(
        encoding="utf-8"
    )
    assert locale_mod._LOCALE_EN[key] in text, (
        f"shell hook missing canonical English fallback for {key!r}"
    )


def _extract_loc_fallbacks_via_ast(path: Path) -> dict[str, str]:
    """Return {locale_key: fallback_string} for every `_loc("KEY", "fallback")`
    or `_resolve_locale_string("KEY") or KEY` callsite. Uses ast so that
    ruff-formatted multi-line implicit-concat string literals are correctly
    re-joined (Python evaluates them at parse time)."""
    src = path.read_text(encoding="utf-8")
    tree = ast.parse(src)
    fallbacks: dict[str, str] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
            continue
        if node.func.id == "_loc" and len(node.args) == 2:
            key_node, fb_node = node.args
            if (
                isinstance(key_node, ast.Constant)
                and isinstance(key_node.value, str)
                and isinstance(fb_node, ast.Constant)
                and isinstance(fb_node.value, str)
            ):
                fallbacks[key_node.value] = fb_node.value
    return fallbacks


@pytest.mark.parametrize(
    "key",
    [
        "SYNC_FOUNDATION_LEAD",
        "SYNC_STRUCTURE_LEAD",
        "SYNC_FOUNDATION_FILES_HEADER",
        "SYNC_STRUCTURE_FILES_HEADER",
        "SYNC_CODEX_RUN_PRIMARY",
        "SYNC_CLAUDE_RUN_ALSO",
        "SYNC_INCOMPLETE_NOTE",
        "SYNC_REVIEW_TARGETS_NOTE",
        "SYNC_REPORT_BOTH_NOTE",
    ],
)
def test_codex_stop_sync_fallback_matches_locale_en(key: str) -> None:
    """Codex Stop hook _loc("KEY", "fallback") fallback values must equal
    _LOCALE_EN[KEY] byte-identically. Uses ast to handle ruff's implicit-
    string-concat across multiple source lines."""
    fallbacks = _extract_loc_fallbacks_via_ast(
        REPO_ROOT / ".codex" / "hooks" / "stop-sync-reminder.py"
    )
    assert key in fallbacks, f"_loc({key!r}, ...) missing in codex stop-sync hook"
    assert fallbacks[key] == locale_mod._LOCALE_EN[key], (
        f"drift: codex hook _loc({key!r}, ...) fallback differs from _LOCALE_EN"
    )


# ---------------------------------------------------------------------------
# 7. AST guard — Hangul only inside _LOCALE_KO mapping VALUES
# ---------------------------------------------------------------------------
def test_locale_py_korean_only_in_locale_ko_dict_values() -> None:
    """Korean must appear ONLY inside _LOCALE_KO mapping value strings.
    Comments, docstrings, _LOCALE_EN values, identifiers must remain ASCII."""
    src = (SHARED_DIR / "governor" / "locale.py").read_text(encoding="utf-8")
    tree = ast.parse(src)

    # 1. Find _LOCALE_KO assignment, assert it is a literal ast.Dict.
    #    Accept both ast.Assign (`_LOCALE_KO = {...}`) and ast.AnnAssign
    #    (`_LOCALE_KO: dict[str, str] = {...}`).
    ko_dict_node: ast.Dict | None = None
    for node in ast.walk(tree):
        target_name: str | None = None
        value_node: ast.expr | None = None
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
        ):
            target_name = node.targets[0].id
            value_node = node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            target_name = node.target.id
            value_node = node.value
        if target_name == "_LOCALE_KO":
            assert isinstance(value_node, ast.Dict), (
                "_LOCALE_KO must be a literal dict (no comprehension / update())"
            )
            ko_dict_node = value_node
            break
    assert ko_dict_node is not None, "_LOCALE_KO assignment not found"

    # 2. Allowed Hangul-bearing string nodes: only direct dict VALUES
    #    (or Constant args inside `\n.join([...])` lists used as values).
    allowed_node_ids: set[int] = set()
    for v in ko_dict_node.values:
        if isinstance(v, ast.Constant) and isinstance(v.value, str):
            allowed_node_ids.add(id(v))
        elif (
            isinstance(v, ast.Call)
            and isinstance(v.func, ast.Attribute)
            and v.func.attr == "join"
            and v.args
            and isinstance(v.args[0], ast.List)
        ):
            for elt in v.args[0].elts:
                if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                    allowed_node_ids.add(id(elt))

    # 3. Every Hangul-bearing string Constant must be in the allowed set.
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and HANGUL_RE.search(node.value)
            and id(node) not in allowed_node_ids
        ):
            pytest.fail(
                f"locale.py line {node.lineno}: Hangul in non-_LOCALE_KO-value "
                f"position: {node.value!r}"
            )

    # 4. Comments — AST does not track them; tokenize separately.
    for tok in tokenize.tokenize(io.BytesIO(src.encode("utf-8")).readline):
        if tok.type == tokenize.COMMENT and HANGUL_RE.search(tok.string):
            pytest.fail(
                f"locale.py line {tok.start[0]}: Hangul in comment: {tok.string!r}"
            )


# ---------------------------------------------------------------------------
# 8. Cycle import guard
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("module_name", ["verify.py", "completion_gate.py"])
def test_no_locale_import_in_canonical_modules(module_name: str) -> None:
    """verify.py and completion_gate.py must NOT import from .locale.
    The dependency direction is one-way: locale -> {verify, completion_gate}."""
    src = (SHARED_DIR / "governor" / module_name).read_text(encoding="utf-8")
    assert "from .locale" not in src
    assert "from governor.locale" not in src
    assert "import locale" not in src.split("# noqa")[0]  # ignore noqa segments


# ---------------------------------------------------------------------------
# 9. CLI mode (-m governor.locale)
# ---------------------------------------------------------------------------
def test_locale_module_cli_mode_via_dash_m_default_english() -> None:
    env = {**os.environ, "PYTHONPATH": str(SHARED_DIR)}
    env.pop("AGENT_LOCALE", None)
    result = subprocess.run(
        [sys.executable, "-m", "governor.locale", "REMINDER_TEXT"],
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.rstrip("\n") == REMINDER_TEXT


def test_locale_module_cli_mode_via_dash_m_ko() -> None:
    env = {**os.environ, "PYTHONPATH": str(SHARED_DIR), "AGENT_LOCALE": "ko"}
    result = subprocess.run(
        [sys.executable, "-m", "governor.locale", "SYNC_STRONG_HEADER"],
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "강력 권장" in result.stdout


# ---------------------------------------------------------------------------
# 10. IC-19 always-fallback callsite guard
# ---------------------------------------------------------------------------
def _build_parent_map(tree: ast.AST) -> dict[int, ast.AST]:
    parents: dict[int, ast.AST] = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parents[id(child)] = parent
    return parents


@pytest.mark.parametrize(
    "rel",
    [
        ".claude/hooks/verify_first.py",
        ".codex/hooks/verify_first.py",
        ".claude/hooks/completion_gate.py",
        ".codex/hooks/completion_gate.py",
        ".codex/hooks/stop-sync-reminder.py",
    ],
)
def test_python_resolver_callsites_have_or_fallback(rel: str) -> None:
    """IC-19: every _resolve_locale_string("KEY") call must be the LEFT
    operand of a `or` BoolOp. _loc("KEY", "fallback") calls must have
    exactly 2 positional args with non-empty string fallback."""
    src = (REPO_ROOT / rel).read_text(encoding="utf-8")
    tree = ast.parse(src)
    parents = _build_parent_map(tree)
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in {"_resolve_locale_string", "_loc"}
        ):
            continue

        if node.func.id == "_loc":
            assert len(node.args) == 2, (
                f"{rel}:{node.lineno}: _loc must be called positionally with 2 args"
            )
            assert not node.keywords, (
                f"{rel}:{node.lineno}: _loc must use positional args (no keyword form)"
            )
            fb = node.args[1]
            assert isinstance(fb, ast.Constant) and isinstance(fb.value, str), (
                f"{rel}:{node.lineno}: _loc fallback must be a string literal"
            )
            assert fb.value, f"{rel}:{node.lineno}: _loc fallback must be non-empty"
            continue

        # _resolve_locale_string("KEY") must be left operand of `or` BoolOp.
        # Skip the fallback def lambdas (they appear inside the except block
        # as `def _resolve_locale_string(key: str) -> str: return ""`).
        parent = parents.get(id(node))
        if parent is None:
            continue
        assert isinstance(parent, ast.BoolOp) and isinstance(parent.op, ast.Or), (
            f"{rel}:{node.lineno}: _resolve_locale_string call not combined with "
            f"`or fallback` (parent={type(parent).__name__})"
        )
        assert parent.values[0] is node, (
            f"{rel}:{node.lineno}: _resolve_locale_string must be the LEFT operand"
        )


def test_shell_resolver_callsites_have_single_quoted_fallback() -> None:
    """Every `_resolve_locale KEY '...'` call in the Bash hook must
    single-quote the fallback so `$sync-guidelines` literals do not
    expand under `set -u`."""
    text = (REPO_ROOT / ".claude" / "hooks" / "stop-sync-reminder.sh").read_text(
        encoding="utf-8"
    )
    # Match `_resolve_locale KEY ARG` where ARG is whatever comes between the
    # key and the closing `)` of the $(...) command substitution.
    pattern = re.compile(r"_resolve_locale\s+(\w+)\s+(.+?)\)", re.MULTILINE)
    callsites = pattern.findall(text)
    assert callsites, "no _resolve_locale callsites found in shell hook"
    for key, arg in callsites:
        stripped = arg.strip()
        assert stripped.startswith("'") and stripped.endswith("'"), (
            f"_resolve_locale {key} fallback must be single-quoted (got: {arg!r})"
        )


# ---------------------------------------------------------------------------
# 11. In-process emission tests
# ---------------------------------------------------------------------------
def _load_codex_stop_sync():
    """Re-import the codex stop-sync module fresh (its top-level was
    refactored to define build_segments + main; importing is now safe
    because nothing executes at top level except function definitions).

    Codex stop-sync does `from _shared import REPO_ROOT, changed_files`
    at import time, so we install Codex `_shared` under the canonical
    name first (same pattern as _load_codex_completion_gate)."""
    codex_hooks = REPO_ROOT / ".codex" / "hooks"
    saved_shared = sys.modules.pop("_shared", None)
    try:
        _load_module("_shared", codex_hooks / "_shared.py")
        return _load_module(
            "codex_stop_sync_test", codex_hooks / "stop-sync-reminder.py"
        )
    finally:
        if saved_shared is not None:
            sys.modules["_shared"] = saved_shared
        else:
            sys.modules.pop("_shared", None)


def test_codex_stop_sync_build_segments_default_english_byte_identical() -> None:
    """Default-locale: build_segments output uses canonical English
    constants byte-identically to the pre-refactor inline strings."""
    m = _load_codex_stop_sync()
    segments = m.build_segments(changed=["src/_core/x.py"])
    assert len(segments) >= 1
    seg0 = segments[0]
    assert "Guideline sync required before closing this work." in seg0
    assert "Foundation files changed:" in seg0
    assert "- src/_core/x.py" in seg0
    assert "Codex: run $sync-guidelines" in seg0
    assert "Claude Code: run /sync-guidelines as well" in seg0
    assert "Sync is incomplete until project-dna" in seg0
    assert "REVIEW targets must be reported" in seg0


def test_codex_stop_sync_build_segments_ko(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AGENT_LOCALE", "ko")
    m = _load_codex_stop_sync()
    segments = m.build_segments(changed=["src/_core/x.py"])
    seg0 = segments[0]
    assert "이 작업을 마무리하기 전에 가이드라인 동기화가 필요합니다" in seg0
    assert "변경된 Foundation 파일:" in seg0
    assert "src/_core/x.py" in seg0  # path stays as-is
    assert "Codex: $sync-guidelines 실행" in seg0  # command token preserved


def test_codex_stop_sync_build_segments_structure_default_english() -> None:
    m = _load_codex_stop_sync()
    segments = m.build_segments(changed=["src/foo/domain/dtos/y.py"])
    assert len(segments) >= 1
    seg0 = segments[0]
    assert "Guideline sync recommended." in seg0
    assert "Domain structure files changed:" in seg0
    assert "- src/foo/domain/dtos/y.py" in seg0
    assert "When you run sync, report both AUTO-FIX and REVIEW" in seg0


def _load_module(name: str, path: Path):
    """Same idiom as tests/unit/agents_shared/test_completion_gate.py::_load —
    spec_from_file_location + exec_module. Does not pop other modules."""
    import importlib.util  # noqa: PLC0415

    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader, f"failed to make spec for {path}"
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _load_codex_completion_gate():
    """Codex completion_gate does `from verify_first import session_id` at
    import time. To be robust against test ordering and cached imports, we
    temporarily install Codex verify_first as `sys.modules['verify_first']`
    while exec'ing the Codex completion_gate, then restore the previous
    binding (if any) so other tests' verify_first references are not
    disturbed."""
    codex_hooks = REPO_ROOT / ".codex" / "hooks"

    saved_vf = sys.modules.pop("verify_first", None)
    saved_shared = sys.modules.pop("_shared", None)
    try:
        # Pre-load Codex verify_first under the canonical name so the
        # `from verify_first import session_id` inside completion_gate.py
        # resolves to the Codex side.
        _load_module("_shared", codex_hooks / "_shared.py")
        _load_module("verify_first", codex_hooks / "verify_first.py")
        return _load_module(
            "codex_completion_gate_test", codex_hooks / "completion_gate.py"
        )
    finally:
        # Restore any prior bindings test_completion_gate.py / others rely on.
        if saved_vf is not None:
            sys.modules["verify_first"] = saved_vf
        else:
            sys.modules.pop("verify_first", None)
        if saved_shared is not None:
            sys.modules["_shared"] = saved_shared
        else:
            sys.modules.pop("_shared", None)


def _load_claude_completion_gate():
    return _load_module(
        "claude_completion_gate_test",
        REPO_ROOT / ".claude" / "hooks" / "completion_gate.py",
    )


def test_codex_completion_gate_emits_ko_segment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Module-bound monkeypatch (R3-F5): patch completion_gate.changed_files
    on the Codex module because the Codex hook does
    `from _shared import changed_files` (binds at import)."""
    cg = _load_codex_completion_gate()

    monkeypatch.setenv("AGENT_LOCALE", "ko")
    monkeypatch.setattr(cg, "changed_files", lambda: [".agents/shared/governor/foo.py"])
    monkeypatch.setattr(cg, "is_log_only_backfill", lambda c: False)
    monkeypatch.setattr(cg, "_read_latest_token", lambda d: None)
    monkeypatch.setattr(cg, "parse_trigger_globs", lambda: [".agents/**"])
    monkeypatch.setattr(cg, "is_governor_changing", lambda c, g: True)
    monkeypatch.setattr(cg, "match_log_entry", lambda c, p: "missing")
    monkeypatch.setattr(cg, "pr_number_from_branch", lambda: 999)

    seg = cg.governor_changing_segment()
    assert seg is not None
    assert "거버너 관련 변경이 감지" in seg
    assert "PR #999" in seg
    assert "{pr}" not in seg


def test_codex_completion_gate_emits_default_english_segment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Default locale: byte-identical to pre-#133 GOVERNOR_REMINDER_WITH_PR."""
    cg = _load_codex_completion_gate()

    monkeypatch.delenv("AGENT_LOCALE", raising=False)
    monkeypatch.setattr(cg, "changed_files", lambda: [".agents/shared/governor/foo.py"])
    monkeypatch.setattr(cg, "is_log_only_backfill", lambda c: False)
    monkeypatch.setattr(cg, "_read_latest_token", lambda d: None)
    monkeypatch.setattr(cg, "parse_trigger_globs", lambda: [".agents/**"])
    monkeypatch.setattr(cg, "is_governor_changing", lambda c, g: True)
    monkeypatch.setattr(cg, "match_log_entry", lambda c, p: "missing")
    monkeypatch.setattr(cg, "pr_number_from_branch", lambda: 999)

    seg = cg.governor_changing_segment()
    assert seg == GOVERNOR_REMINDER_WITH_PR.format(pr=999)


def test_claude_completion_gate_emits_ko_segment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Claude side uses `_changed_files` (underscore wrapper) — different
    helper name from Codex but same emit-pattern coverage."""
    cg = _load_claude_completion_gate()

    monkeypatch.setenv("AGENT_LOCALE", "ko")
    monkeypatch.setattr(
        cg, "_changed_files", lambda: [".agents/shared/governor/foo.py"]
    )
    monkeypatch.setattr(cg, "is_log_only_backfill", lambda c: False)
    monkeypatch.setattr(cg, "_read_latest_token", lambda d: None)
    monkeypatch.setattr(cg, "parse_trigger_globs", lambda: [".agents/**"])
    monkeypatch.setattr(cg, "is_governor_changing", lambda c, g: True)
    monkeypatch.setattr(cg, "match_log_entry", lambda c, p: "missing")
    monkeypatch.setattr(cg, "pr_number_from_branch", lambda: 999)

    seg = cg.governor_changing_segment()
    assert seg is not None
    assert "거버너 관련 변경이 감지" in seg
    assert "PR #999" in seg


# ---------------------------------------------------------------------------
# 12. Shell subprocess in temp git repo (R3-F6 + R4-F7)
# ---------------------------------------------------------------------------
def _setup_temp_repo(tmp_path: Path) -> Path:
    """Init a temp git repo with a foundation file untracked. The shell
    hook treats untracked files as 'changed', so no `git commit` is
    needed (avoids user.name/user.email requirement)."""
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    foundation_file = tmp_path / "src" / "_core" / "x.py"
    foundation_file.parent.mkdir(parents=True)
    foundation_file.write_text("# stub\n")

    hook_dir = tmp_path / ".claude" / "hooks"
    hook_dir.mkdir(parents=True)
    import shutil  # noqa: PLC0415

    shutil.copy(
        REPO_ROOT / ".claude" / "hooks" / "stop-sync-reminder.sh",
        hook_dir / "stop-sync-reminder.sh",
    )
    shutil.copy(
        REPO_ROOT / ".claude" / "hooks" / "completion_gate.py",
        hook_dir / "completion_gate.py",
    )
    (tmp_path / ".agents").mkdir()
    (tmp_path / ".agents" / "shared").symlink_to(SHARED_DIR, target_is_directory=True)
    return hook_dir / "stop-sync-reminder.sh"


def test_claude_stop_sync_shell_emits_default_english(tmp_path: Path) -> None:
    hook = _setup_temp_repo(tmp_path)
    env = {k: v for k, v in os.environ.items() if k != "AGENT_LOCALE"}
    result = subprocess.run(
        ["bash", str(hook)], cwd=tmp_path, env=env, capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
    assert "/sync-guidelines strongly recommended" in result.stdout
    assert "Foundation files changed:" in result.stdout
    assert "src/_core/x.py" in result.stdout
    assert "Claude: run /sync-guidelines" in result.stdout
    assert "Codex: also run $sync-guidelines" in result.stdout
    assert "강력 권장" not in result.stdout  # regression guard


def test_claude_stop_sync_shell_emits_ko(tmp_path: Path) -> None:
    hook = _setup_temp_repo(tmp_path)
    env = {**os.environ, "AGENT_LOCALE": "ko"}
    result = subprocess.run(
        ["bash", str(hook)], cwd=tmp_path, env=env, capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
    assert "/sync-guidelines 강력 권장" in result.stdout
    assert "변경된 Foundation 파일:" in result.stdout
    assert "src/_core/x.py" in result.stdout  # path preserved
    assert "Claude: /sync-guidelines 실행" in result.stdout
    assert "Codex: $sync-guidelines도 실행" in result.stdout


# ---------------------------------------------------------------------------
# 13. Bash 3.2 syntax check (macOS default)
# ---------------------------------------------------------------------------
def test_shell_hook_passes_bash_n_syntax_check() -> None:
    """`bash -n` must succeed under macOS bash 3.2.x — no bash 4+ syntax."""
    result = subprocess.run(
        ["bash", "-n", str(REPO_ROOT / ".claude" / "hooks" / "stop-sync-reminder.sh")],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"bash -n failed: {result.stderr}"
