"""Shared governor policy (Tier B). Consumed by Claude/Codex hook adapters.

Boundary: this package owns governor *policy* — token vocab, lifecycle, gate
logic, reminder text, glob matching. Tool-specific runtime utilities (e.g.
``.codex/hooks/_shared.py`` git/subprocess helpers, Codex session tracking)
remain per-tool and are not duplicated here.

Phase 5 (#124) consolidates duplicate helpers from Phase 2/3/4 hook scripts
into this single package. Hook scripts under ``.claude/hooks/`` and
``.codex/hooks/`` import from here as thin shims.

Public API is declared via ``__all__`` and grows as Phase 5 commits land:
    commit 1 — paths, time_window
    commit 2 — tokens, markers (lifecycle), safety
    commit 3 — verify
    commit 4 — completion_gate (GateResult)
"""

from .completion_gate import (
    GOVERNOR_REMINDER_NO_PR,
    GOVERNOR_REMINDER_WITH_PR,
    GOVERNOR_REVIEW_LOG_PREFIX,
    GateResult,
    changed_files_via_git,
    evaluate_gate,
    governor_changing_segment,
    is_governor_changing,
    is_log_only_backfill,
    match_log_entry,
    parse_trigger_globs,
    pr_number_from_branch,
    render_reminder,
)
from .markers import (
    MarkerLifecycle,
    consume_phase2_markers,
    read_latest_token,
    write_marker,
)
from .paths import GOVERNOR_PATHS_MD, REPO_ROOT
from .safety import (
    PROMPT_RULES,
    Blocked,
    ParsedToken,
    SafeParseResult,
    check_safety,
    safe_parse_exception_token,
)
from .time_window import _within_24h
from .tokens import EXPLORATION_TOKENS, TOKEN_REGEX, parse_exception_token
from .verify import (
    REMINDER_TEXT,
    extract_file_path,
    is_python_source,
    should_remind_claude,
)

__all__ = [
    "Blocked",
    "EXPLORATION_TOKENS",
    "GOVERNOR_PATHS_MD",
    "GOVERNOR_REMINDER_NO_PR",
    "GOVERNOR_REMINDER_WITH_PR",
    "GOVERNOR_REVIEW_LOG_PREFIX",
    "GateResult",
    "MarkerLifecycle",
    "PROMPT_RULES",
    "ParsedToken",
    "REMINDER_TEXT",
    "REPO_ROOT",
    "SafeParseResult",
    "TOKEN_REGEX",
    "_within_24h",
    "changed_files_via_git",
    "check_safety",
    "consume_phase2_markers",
    "evaluate_gate",
    "extract_file_path",
    "governor_changing_segment",
    "is_governor_changing",
    "is_log_only_backfill",
    "is_python_source",
    "match_log_entry",
    "parse_exception_token",
    "parse_trigger_globs",
    "pr_number_from_branch",
    "read_latest_token",
    "render_reminder",
    "safe_parse_exception_token",
    "should_remind_claude",
    "write_marker",
]
