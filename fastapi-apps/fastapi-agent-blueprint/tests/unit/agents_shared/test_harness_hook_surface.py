from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_TOOLS_DIR = _REPO_ROOT / "tools"
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))

from check_harness_hook_surface import check_root  # noqa: E402


def _write_codex_hooks(root: Path, command: str) -> None:
    path = root / ".codex" / "hooks.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "hooks": {
                    "Stop": [
                        {
                            "hooks": [
                                {"type": "command", "command": command},
                            ]
                        }
                    ]
                }
            }
        ),
        encoding="utf-8",
    )


def test_hook_surface_accepts_shared_launcher(tmp_path: Path) -> None:
    _write_codex_hooks(
        tmp_path,
        "sh .agents/shared/harness-python.sh .codex/hooks/stop-sync-reminder.py",
    )
    shell = tmp_path / ".claude" / "hooks" / "stop-sync-reminder.sh"
    shell.parent.mkdir(parents=True, exist_ok=True)
    shell.write_text(
        'sh "$PY_LAUNCHER" -m governor.locale KEY\n',
        encoding="utf-8",
    )

    assert check_root(tmp_path) == []


def test_hook_surface_rejects_codex_bare_python3(tmp_path: Path) -> None:
    _write_codex_hooks(tmp_path, "python3 .codex/hooks/stop-sync-reminder.py")

    violations = check_root(tmp_path)

    assert len(violations) == 1
    assert ".codex/hooks.json" in str(violations[0].path)


def test_hook_surface_rejects_claude_pipe_to_python3(tmp_path: Path) -> None:
    _write_codex_hooks(
        tmp_path,
        "sh .agents/shared/harness-python.sh .codex/hooks/stop-sync-reminder.py",
    )
    shell = tmp_path / ".claude" / "hooks" / "user-prompt-submit.sh"
    shell.parent.mkdir(parents=True, exist_ok=True)
    shell.write_text(
        'echo "$INPUT" | python3 "$(dirname "$0")/user_prompt_submit.py"\n',
        encoding="utf-8",
    )

    violations = check_root(tmp_path)

    assert len(violations) == 1
    assert "python3" in violations[0].text


def test_hook_surface_ignores_comments(tmp_path: Path) -> None:
    _write_codex_hooks(
        tmp_path,
        "sh .agents/shared/harness-python.sh .codex/hooks/stop-sync-reminder.py",
    )
    shell = tmp_path / ".claude" / "hooks" / "stop-sync-reminder.sh"
    shell.parent.mkdir(parents=True, exist_ok=True)
    shell.write_text(
        "# python3 is mentioned in a non-executable comment\n", encoding="utf-8"
    )

    assert check_root(tmp_path) == []
