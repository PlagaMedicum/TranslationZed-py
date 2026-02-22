"""Regression tests for formatter script contracts used by verify gates."""

from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path


def _repo_root() -> Path:
    """Return repository root path for subprocess script execution."""
    return Path(__file__).resolve().parents[1]


def _write_fake_python(path: Path, *, args_log: Path) -> None:
    """Write fake Python runner that records arguments and exits successfully."""
    path.write_text(
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "set -euo pipefail",
                'printf "__CALL__\\n" >> "${FAKE_FMT_ARGS_LOG}"',
                'printf "%s\\n" "$@" >> "${FAKE_FMT_ARGS_LOG}"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    path.chmod(path.stat().st_mode | stat.S_IEXEC)


def _read_calls(log_path: Path) -> list[list[str]]:
    """Parse fake-runner argument log into invocation call lists."""
    calls: list[list[str]] = []
    current: list[str] = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        if line == "__CALL__":
            if current:
                calls.append(current)
            current = []
            continue
        current.append(line)
    if current:
        calls.append(current)
    return calls


def test_fmt_changed_scope_formats_only_changed_python_sources(tmp_path: Path) -> None:
    """Changed-scope fmt should invoke black with changed Python files only."""
    repo = _repo_root()
    fake_python = tmp_path / "fake-python.sh"
    args_log = tmp_path / "fmt-args.log"
    _write_fake_python(fake_python, args_log=args_log)

    probe = repo / "tests" / "_fmt_changed_scope_probe.py"
    probe.write_text('"""probe"""\n', encoding="utf-8")
    try:
        env = dict(os.environ)
        env.update(
            {
                "VENV_PY_OVERRIDE": str(fake_python),
                "FMT_SCOPE": "changed",
                "FAKE_FMT_ARGS_LOG": str(args_log),
            }
        )
        proc = subprocess.run(
            ["bash", "scripts/fmt.sh"],
            cwd=repo,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
    finally:
        probe.unlink(missing_ok=True)

    assert proc.returncode == 0
    calls = _read_calls(args_log)
    assert calls
    assert all(call[:2] == ["-m", "black"] for call in calls)

    targets_by_call = [
        [value for value in call if value.endswith(".py")] for call in calls
    ]
    assert all(targets for targets in targets_by_call)
    assert any(
        "tests/_fmt_changed_scope_probe.py" in targets for targets in targets_by_call
    )
    assert all(
        target.startswith(("translationzed_py/", "tests/", "scripts/"))
        for targets in targets_by_call
        for target in targets
    )


def test_fmt_script_rejects_invalid_scope(tmp_path: Path) -> None:
    """Invalid fmt scope should fail with explicit usage guidance."""
    repo = _repo_root()
    fake_python = tmp_path / "fake-python.sh"
    args_log = tmp_path / "fmt-args.log"
    _write_fake_python(fake_python, args_log=args_log)

    env = dict(os.environ)
    env.update(
        {
            "VENV_PY_OVERRIDE": str(fake_python),
            "FMT_SCOPE": "invalid",
            "FAKE_FMT_ARGS_LOG": str(args_log),
        }
    )
    proc = subprocess.run(
        ["bash", "scripts/fmt.sh"],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 2
    assert "invalid FMT_SCOPE" in proc.stderr
    assert not args_log.exists()


def test_fmt_check_uses_file_list_and_not_directory_targets(tmp_path: Path) -> None:
    """fmt-check should pass explicit Python file paths to black check mode."""
    repo = _repo_root()
    fake_python = tmp_path / "fake-python.sh"
    args_log = tmp_path / "fmt-check-args.log"
    _write_fake_python(fake_python, args_log=args_log)

    env = dict(os.environ)
    env.update(
        {
            "VENV_PY_OVERRIDE": str(fake_python),
            "FAKE_FMT_ARGS_LOG": str(args_log),
        }
    )
    proc = subprocess.run(
        ["bash", "scripts/fmt_check.sh"],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0
    calls = _read_calls(args_log)
    assert calls
    assert all(call[:4] == ["-m", "black", "--check", "--fast"] for call in calls)
    targets_by_call = [
        [value for value in call if value.endswith(".py")] for call in calls
    ]
    assert all(targets for targets in targets_by_call)
    assert all(
        target.startswith(("translationzed_py/", "tests/", "scripts/"))
        for targets in targets_by_call
        for target in targets
    )
