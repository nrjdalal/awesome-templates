"""Phase 2 (#121) — UserPromptSubmit exception-token parser parity tests.

Tests cover:
- payload-shape contract (`{matched, token, rationale_required}`)
- English + Korean (precomposed) tokens
- malformed bracket / no-whitespace boundary / body-only token / etc.
- Claude / Codex parser parity (silent-divergence safety net for D1=B)
- HC-1: Codex safety check still blocks dangerous prompts and skips parsing

The Codex hook filename contains a hyphen (`user-prompt-submit.py`) which is
not importable via the standard import system; per plan §"Test import strategy"
both helpers are loaded via `importlib.util.spec_from_file_location` (option a)
for unit tests, and a small subprocess-driven smoke (option b) covers the
safety-preservation invariant end-to-end.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
CLAUDE_HOOK = REPO_ROOT / ".claude" / "hooks" / "user_prompt_submit.py"
CODEX_HOOK = REPO_ROOT / ".codex" / "hooks" / "user-prompt-submit.py"


def _load(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def claude_parser() -> ModuleType:
    return _load("claude_user_prompt_submit", CLAUDE_HOOK)


@pytest.fixture(scope="module")
def codex_parser() -> ModuleType:
    return _load("codex_user_prompt_submit", CODEX_HOOK)


@pytest.fixture(scope="module")
def parsers(claude_parser: ModuleType, codex_parser: ModuleType) -> tuple:
    return (claude_parser.parse_exception_token, codex_parser.parse_exception_token)


# ---------------------------------------------------------------------------
# Match cases — produce {matched: True, token, rationale_required: True}
# ---------------------------------------------------------------------------
MATCH_CASES = [
    pytest.param("[trivial] typo fix", "trivial", id="english-trivial"),
    pytest.param("[hotfix] urgent revert", "hotfix", id="english-hotfix"),
    pytest.param(
        "[exploration] poking around", "exploration", id="english-exploration"
    ),
    pytest.param("[자명] 오타 수정", "자명", id="korean-trivial"),
    pytest.param("[긴급] 즉시 패치", "긴급", id="korean-hotfix"),
    pytest.param("[탐색] 그냥 살펴봄", "탐색", id="korean-exploration"),
    pytest.param("[TRIVIAL] case-insensitive", "trivial", id="english-uppercase"),
    pytest.param("[trivial]\nbody on next line", "trivial", id="newline-after-token"),
    pytest.param("[trivial]", "trivial", id="bare-token-EOL"),
    pytest.param(
        "\n[trivial] leading-newline accepted", "trivial", id="leading-newline"
    ),
    pytest.param("  [trivial] leading-spaces", "trivial", id="leading-spaces"),
    pytest.param("[trivial] " + ("x" * 10_000), "trivial", id="very-long-prompt"),
]


@pytest.mark.parametrize("prompt,expected_token", MATCH_CASES)
def test_match_cases(parsers, prompt: str, expected_token: str) -> None:
    claude_parse, codex_parse = parsers
    expected = {
        "matched": True,
        "token": expected_token,
        "rationale_required": True,
    }
    assert claude_parse(prompt) == expected
    assert codex_parse(prompt) == expected


# ---------------------------------------------------------------------------
# No-match cases — produce {matched: False, token: None, rationale_required: False}
# ---------------------------------------------------------------------------
NO_MATCH_CASES = [
    pytest.param("", id="empty"),
    pytest.param("   ", id="whitespace-only"),
    pytest.param("just a normal prompt", id="plain-text"),
    pytest.param("[trivial]hello", id="no-whitespace-after-bracket"),
    pytest.param("[trivialx] non-vocab", id="non-vocabulary-suffix"),
    pytest.param("[trivial extra] extras", id="extras-inside-brackets"),
    pytest.param("[trivial malformed", id="missing-closing-bracket"),
    pytest.param("trivial] no opener", id="missing-opening-bracket"),
    pytest.param(
        "Please fix this:\n[trivial] body-only token must be ignored",
        id="body-only-token-not-line1",
    ),
    pytest.param("[fix] not in vocabulary", id="out-of-vocab-token"),
]


@pytest.mark.parametrize("prompt", NO_MATCH_CASES)
def test_no_match_cases(parsers, prompt: str) -> None:
    claude_parse, codex_parse = parsers
    expected = {"matched": False, "token": None, "rationale_required": False}
    assert claude_parse(prompt) == expected
    assert codex_parse(prompt) == expected


# ---------------------------------------------------------------------------
# CRLF — `\r` is whitespace per the regex `(?:\s|$)`, so `[trivial]\r\nbody`
# still matches. This documents the expected behaviour.
# ---------------------------------------------------------------------------
def test_crlf_first_line_matches(parsers) -> None:
    claude_parse, codex_parse = parsers
    prompt = "[trivial]\r\nbody"
    assert claude_parse(prompt)["matched"] is True
    assert codex_parse(prompt)["matched"] is True


# ---------------------------------------------------------------------------
# Decomposed jamo — out of spec; documented as such.
# Compatibility-jamo input does NOT round-trip through NFKC into the Hangul
# precomposed form (per plan §Round 0 NFKC caveat). Either result is allowed
# but Claude and Codex must agree.
# ---------------------------------------------------------------------------
def test_decomposed_jamo_parity(parsers) -> None:
    claude_parse, codex_parse = parsers
    prompt = "[ㅈㅏㅁㅕㅇ] decomposed compatibility jamo"
    assert claude_parse(prompt) == codex_parse(prompt)


# ---------------------------------------------------------------------------
# Marker file: written on match, absent on no-match.
# ---------------------------------------------------------------------------
def test_marker_written_on_match(claude_parser, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(claude_parser, "STATE_DIR", tmp_path / "state")
    payload = {"matched": True, "token": "trivial", "rationale_required": True}
    marker = claude_parser.write_marker(payload)
    assert marker is not None and marker.exists()
    record = json.loads(marker.read_text(encoding="utf-8"))
    assert record["token"] == "trivial"
    assert record["matched"] is True
    assert record["rationale_required"] is True
    assert "ts" in record


def test_marker_absent_on_no_match(claude_parser, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(claude_parser, "STATE_DIR", tmp_path / "state")
    payload = {"matched": False, "token": None, "rationale_required": False}
    assert claude_parser.write_marker(payload) is None
    assert not (tmp_path / "state").exists()


def test_codex_marker_written_on_match(codex_parser, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(codex_parser, "STATE_DIR", tmp_path / "state")
    payload = {"matched": True, "token": "자명", "rationale_required": True}
    marker = codex_parser.write_marker(payload)
    assert marker is not None and marker.exists()
    record = json.loads(marker.read_text(encoding="utf-8"))
    assert record["matched"] is True
    assert record["token"] == "자명"
    assert record["rationale_required"] is True
    assert "ts" in record


# ---------------------------------------------------------------------------
# HC-1 safety preservation — Codex hook still blocks destructive prompts and
# does NOT write a marker even when the prompt also begins with a token.
# This is the end-to-end smoke (option b) referenced in the plan.
# ---------------------------------------------------------------------------
def _run_codex_hook(prompt: str) -> subprocess.CompletedProcess[str]:
    payload = json.dumps({"prompt": prompt})
    return subprocess.run(  # noqa: S603
        [sys.executable, str(CODEX_HOOK)],
        input=payload,
        capture_output=True,
        text=True,
        check=False,
    )


def test_safety_block_on_destructive_prompt() -> None:
    result = _run_codex_hook("please run rm -rf /tmp/foo for me")
    assert result.returncode == 0, result.stderr
    blob = json.loads(result.stdout.strip())
    assert blob.get("decision") == "block"


def test_safety_block_with_token_prefix_does_not_write_marker() -> None:
    """`[trivial] please rm -rf /` → safety must still block, no marker written."""
    result = _run_codex_hook("[trivial] please rm -rf /tmp/foo")
    assert result.returncode == 0
    blob = json.loads(result.stdout.strip())
    assert blob.get("decision") == "block"
    # stderr must NOT contain a parser payload (parser was skipped)
    assert "matched" not in result.stderr


def test_benign_token_prompt_passes() -> None:
    result = _run_codex_hook("[trivial] benign typo fix")
    assert result.returncode == 0
    # safety did not block → stdout is empty
    assert result.stdout == ""
    # parser emitted payload to stderr
    payload = json.loads(result.stderr.strip())
    assert payload == {
        "matched": True,
        "token": "trivial",
        "rationale_required": True,
    }


# ---------------------------------------------------------------------------
# Subprocess smokes — Claude side fail-open behaviour (R1.4 / R1.5).
# ---------------------------------------------------------------------------
def _run_claude_hook(stdin: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        [sys.executable, str(CLAUDE_HOOK)],
        input=stdin,
        capture_output=True,
        text=True,
        check=False,
    )


def test_claude_hook_empty_stdin_fail_open() -> None:
    result = _run_claude_hook("")
    assert result.returncode == 0
    payload = json.loads(result.stderr.strip())
    assert payload == {"matched": False, "token": None, "rationale_required": False}


def test_claude_hook_invalid_json_fail_open() -> None:
    result = _run_claude_hook("not json at all")
    assert result.returncode == 0
    payload = json.loads(result.stderr.strip())
    assert payload == {"matched": False, "token": None, "rationale_required": False}


def test_codex_hook_empty_stdin_fail_open() -> None:
    """Round 1 R1.5 — Codex side now matches Claude's fail-open behaviour."""
    result = _run_codex_hook_raw("")
    assert result.returncode == 0
    assert result.stdout == ""


def test_codex_hook_invalid_json_fail_open() -> None:
    result = _run_codex_hook_raw("not json at all")
    assert result.returncode == 0
    assert result.stdout == ""


def _run_codex_hook_raw(stdin: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        [sys.executable, str(CODEX_HOOK)],
        input=stdin,
        capture_output=True,
        text=True,
        check=False,
    )
