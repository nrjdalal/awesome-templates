"""Locale-resolved hook reminder strings (issue #133, AGENT_LOCALE).

This module is the canonical runtime source for translated terminal output
emitted by Claude / Codex hooks. ``AGENT_LOCALE`` (process env) selects the
language; missing or unknown values fall back to English. Resolution happens
at hook *emit* time (not module import time) so test isolation via
``monkeypatch.setenv`` works without re-importing the package.

Usage from a hook (always combine with an English fallback):

    text = get_locale_string("REMINDER_TEXT") or REMINDER_TEXT

CLI mode (used by ``.claude/hooks/stop-sync-reminder.sh`` so a Bash file does
not need to embed translated strings):

    PYTHONPATH=.agents/shared python3 -m governor.locale SYNC_STRONG_HEADER

Direct path execution (``python3 .agents/shared/governor/locale.py``) is not
supported because ``from .verify import REMINDER_TEXT`` is a package-relative
import.

This file is the only entry in
``tools/check_language_policy.py::LOCALE_DATA_FILES``. Korean strings are
permitted only inside ``_LOCALE_KO`` mapping values; comments, docstrings,
identifiers, and ``_LOCALE_EN`` values must remain ASCII (enforced by
``tests/unit/agents_shared/test_locale.py::test_locale_py_korean_only_in_locale_ko_dict_values``).
"""

from __future__ import annotations

import os
import sys

from .completion_gate import GOVERNOR_REMINDER_NO_PR, GOVERNOR_REMINDER_WITH_PR
from .verify import REMINDER_TEXT

# Re-export canonical English constants from their source modules so the
# default-locale path is byte-identical to the existing constants by
# construction (drift impossible). The 15 ``SYNC_*`` keys below are unique to
# this module; their English values are mirrored in the hook fallback
# arguments and asserted by drift-guard tests.
_LOCALE_EN: dict[str, str] = {
    "REMINDER_TEXT": REMINDER_TEXT,
    "GOVERNOR_REMINDER_WITH_PR": GOVERNOR_REMINDER_WITH_PR,
    "GOVERNOR_REMINDER_NO_PR": GOVERNOR_REMINDER_NO_PR,
    # Sync advisory headers / footers (Claude shell + Codex Python hook).
    "SYNC_STRONG_HEADER": "=== /sync-guidelines strongly recommended ===",
    "SYNC_STRONG_FOOTER": "=============================================",
    "SYNC_NORM_HEADER": "=== /sync-guidelines recommended ===",
    "SYNC_NORM_FOOTER": "====================================",
    # File-list section headers.
    "SYNC_FOUNDATION_FILES_HEADER": "Foundation files changed:",
    "SYNC_STRUCTURE_FILES_HEADER": "Domain structure files changed:",
    # Run-sync action lines (command tokens stay English).
    "SYNC_CLAUDE_RUN": "Claude: run /sync-guidelines",
    "SYNC_CODEX_RUN_ALSO": "Codex: also run $sync-guidelines",
    "SYNC_CODEX_RUN_PRIMARY": "Codex: run $sync-guidelines",
    "SYNC_CLAUDE_RUN_ALSO": "Claude Code: run /sync-guidelines as well",
    # Codex stop-sync notes.
    "SYNC_INCOMPLETE_NOTE": (
        "Sync is incomplete until project-dna, AUTO-FIX, REVIEW, "
        "and Remaining are all reported."
    ),
    "SYNC_REVIEW_TARGETS_NOTE": (
        "REVIEW targets must be reported even when no automatic doc edit is needed."
    ),
    "SYNC_REPORT_BOTH_NOTE": (
        "When you run sync, report both AUTO-FIX and REVIEW targets before closing."
    ),
    # Codex stop-sync lead lines (strong vs normal).
    "SYNC_FOUNDATION_LEAD": "Guideline sync required before closing this work.",
    "SYNC_STRUCTURE_LEAD": "Guideline sync recommended.",
}


_LOCALE_KO: dict[str, str] = {
    "REMINDER_TEXT": "\n".join(
        [
            "[verify-first] 변경된 .py 파일에 대한 검증 단계가 빠진 것 같습니다.",
            "계속하기 전에 테스트나 정적 검사를 실행하세요.",
            "Suggested next: `/test-domain run <domain>` (또는 `pytest tests/unit/<domain>/`)",
            "의도적으로 탐색 중이라면 `[exploration]` / `[탐색]` 접두사로 이 알림을 숨길 수 있습니다.",
        ]
    ),
    "GOVERNOR_REMINDER_WITH_PR": "\n".join(
        [
            "[completion-gate] 거버너 관련 변경이 감지되었습니다 (Pillar 7).",
            "PR #{pr} 본문에 `## Governor Footer` 블록이 있어야 합니다.",
            "CI는 tools/check_governor_footer.py --require-governor-footer 로 검증합니다.",
            "참조: docs/history/047-governor-review-provenance-consolidation.md (D2/D5).",
        ]
    ),
    "GOVERNOR_REMINDER_NO_PR": "\n".join(
        [
            "[completion-gate] 거버너 관련 변경이 감지되었습니다 (Pillar 7).",
            "PR 번호를 알 수 없습니다. 먼저 PR을 연 뒤 본문에 `## Governor Footer` 블록을 채우세요.",
            "참조: docs/history/047-governor-review-provenance-consolidation.md (D2/D5).",
        ]
    ),
    "SYNC_STRONG_HEADER": "=== /sync-guidelines 강력 권장 ===",
    "SYNC_STRONG_FOOTER": "=============================================",
    "SYNC_NORM_HEADER": "=== /sync-guidelines 권장 ===",
    "SYNC_NORM_FOOTER": "====================================",
    "SYNC_FOUNDATION_FILES_HEADER": "변경된 Foundation 파일:",
    "SYNC_STRUCTURE_FILES_HEADER": "변경된 도메인 구조 파일:",
    "SYNC_CLAUDE_RUN": "Claude: /sync-guidelines 실행",
    "SYNC_CODEX_RUN_ALSO": "Codex: $sync-guidelines도 실행",
    "SYNC_CODEX_RUN_PRIMARY": "Codex: $sync-guidelines 실행",
    "SYNC_CLAUDE_RUN_ALSO": "Claude Code: /sync-guidelines도 실행",
    "SYNC_INCOMPLETE_NOTE": (
        "project-dna, AUTO-FIX, REVIEW, Remaining을 모두 보고해야 동기화가 완료됩니다."
    ),
    "SYNC_REVIEW_TARGETS_NOTE": (
        "자동 문서 편집이 없는 경우에도 REVIEW 대상은 반드시 보고해야 합니다."
    ),
    "SYNC_REPORT_BOTH_NOTE": (
        "동기화 실행 후 마무리하기 전에 AUTO-FIX와 REVIEW 대상을 모두 보고하세요."
    ),
    "SYNC_FOUNDATION_LEAD": "이 작업을 마무리하기 전에 가이드라인 동기화가 필요합니다.",
    "SYNC_STRUCTURE_LEAD": "가이드라인 동기화를 권장합니다.",
}


_LOCALES: dict[str, dict[str, str]] = {"en": _LOCALE_EN, "ko": _LOCALE_KO}


def get_locale_string(key: str) -> str:
    """Return locale-resolved string for ``key``.

    Reads ``AGENT_LOCALE`` from ``os.environ`` on every call (do not cache).
    Unknown locale, missing key, or empty translation falls back to the
    English value. Returns ``""`` only if the key is absent from
    ``_LOCALE_EN`` too — callers must combine the result with an English
    fallback (``get_locale_string("K") or K``) per IC-19.
    """
    locale = os.environ.get("AGENT_LOCALE", "en").lower().strip()
    table = _LOCALES.get(locale, _LOCALE_EN)
    return table.get(key) or _LOCALE_EN.get(key, "")


def main(argv: list[str]) -> int:
    """CLI entry point: print the resolved string for the given key.

    Used by ``.claude/hooks/stop-sync-reminder.sh`` so the Bash file does not
    need to embed translated strings.
    """
    if not argv:
        return 2
    print(get_locale_string(argv[0]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
