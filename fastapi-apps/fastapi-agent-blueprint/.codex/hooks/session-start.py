from __future__ import annotations

import contextlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
_SHARED = REPO_ROOT / ".agents" / "shared"
if str(_SHARED) not in sys.path:
    sys.path.insert(0, str(_SHARED))

harness_lines = [
    "Codex repo harness active:",
    "- Shared rules: AGENTS.md",
    "- Repo workflows: .agents/skills/",
    "- Command hooks: .codex/hooks.json",
    "- Reasoning-level guards (F/G/H/I) live in AGENTS.md § Reasoning-Level Consistency Guards; they apply to every conversation and review step, not only PR-level work.",
    "- Use `codex -p research` or `codex --search` only when live web search is actually needed.",
    "- If context feels tight, keep root AGENTS.md short and prefer named skills; AGENTS.override.md is acceptable only when explicitly subject to the same governance as AGENTS.md.",
    "- Codex memories are personal/session optimization, not the team's canonical rules.",
]

# Work-ledger context injection (fail-open per HC-5.5).
work_summary: str | None = None
with contextlib.suppress(Exception):
    from work_ledger import build_session_summary  # noqa: PLC0415

    work_summary = build_session_summary()

parts = ["\n".join(harness_lines)]
if work_summary:
    parts.append(work_summary)

print(json.dumps({"systemMessage": "\n\n".join(parts)}))
