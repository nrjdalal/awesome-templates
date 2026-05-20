from __future__ import annotations

import os
import subprocess
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_LAUNCHER = _REPO_ROOT / ".agents" / "shared" / "harness-python.sh"


def _run_launcher(
    *args: str,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    run_env = os.environ.copy()
    run_env["HARNESS_LAUNCHER_STRICT"] = "1"
    if env:
        run_env.update(env)
    return subprocess.run(
        ["sh", str(_LAUNCHER), *args],
        cwd=cwd or _REPO_ROOT,
        env=run_env,
        capture_output=True,
        text=True,
        check=False,
    )


def _write_executable(path: Path, body: str) -> None:
    path.write_text(body, encoding="utf-8")
    path.chmod(0o755)


def test_launcher_prefers_project_venv_python() -> None:
    proc = _run_launcher("-c", "import sys; print(sys.executable)")
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == str(_REPO_ROOT / ".venv" / "bin" / "python")


def test_launcher_detects_repo_root_outside_repo_cwd(tmp_path: Path) -> None:
    proc = _run_launcher("-c", "import os; print(os.getcwd())", cwd=tmp_path)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == str(_REPO_ROOT)


def test_launcher_falls_back_to_uv_run_no_sync(tmp_path: Path) -> None:
    fake_uv = tmp_path / "uv"
    _write_executable(
        fake_uv,
        """#!/usr/bin/env sh
if [ "$1" = "run" ] && [ "$2" = "--no-sync" ] && [ "$3" = "python" ]; then
    shift 3
    case "$2" in
        *version_info*) exit 0 ;;
        *) printf '%s\\n' "uv-ok"; exit 0 ;;
    esac
fi
exit 9
""",
    )

    proc = _run_launcher(
        "-c",
        "print('ignored by fake uv')",
        env={
            "HARNESS_PYTHON_DISABLE_VENV": "1",
            "HARNESS_PYTHON_DISABLE_SYSTEM": "1",
            "PATH": f"{tmp_path}:{os.environ.get('PATH', '')}",
        },
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == "uv-ok"


def test_launcher_rejects_incompatible_system_python(tmp_path: Path) -> None:
    fake_python = tmp_path / "python39"
    _write_executable(
        fake_python,
        """#!/usr/bin/env sh
if [ "$1" = "-c" ]; then
    exit 1
fi
exit 0
""",
    )

    proc = _run_launcher(
        "-c",
        "print('should not run')",
        env={
            "HARNESS_PYTHON_DISABLE_VENV": "1",
            "HARNESS_PYTHON_DISABLE_UV": "1",
            "HARNESS_PYTHON_SYSTEM_CANDIDATES": str(fake_python),
        },
    )
    assert proc.returncode == 127
    assert "no compatible Python interpreter found" in proc.stderr


def test_launcher_accepts_compatible_system_python(tmp_path: Path) -> None:
    fake_python = tmp_path / "python312"
    _write_executable(
        fake_python,
        """#!/usr/bin/env sh
if [ "$1" = "-c" ]; then
    case "$2" in
        *version_info*) exit 0 ;;
        *) printf '%s\\n' "system-ok"; exit 0 ;;
    esac
fi
exit 0
""",
    )

    proc = _run_launcher(
        "-c",
        "print('ignored by fake python')",
        env={
            "HARNESS_PYTHON_DISABLE_VENV": "1",
            "HARNESS_PYTHON_DISABLE_UV": "1",
            "HARNESS_PYTHON_SYSTEM_CANDIDATES": str(fake_python),
        },
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == "system-ok"
