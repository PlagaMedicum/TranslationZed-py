"""Regression tests for deterministic packaging-script contracts."""

from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path

from tests._bash_exec import resolve_bash_executable

ROOT = Path(__file__).resolve().parents[1]


def test_pack_shell_fails_without_preinstalled_pyinstaller(tmp_path: Path) -> None:
    """The shell packer should diagnose a missing prerequisite without installing it."""
    fake_python = tmp_path / "python"
    args_log = tmp_path / "args.log"
    fake_python.write_text(
        '#!/usr/bin/env bash\nprintf "%s\\n" "$@" > "$PACK_ARGS_LOG"\nexit 1\n',
        encoding="utf-8",
    )
    fake_python.chmod(fake_python.stat().st_mode | stat.S_IEXEC)
    env = dict(os.environ)
    env.update(
        {
            "VENV_PY_OVERRIDE": str(fake_python),
            "PACK_ARGS_LOG": str(args_log),
        }
    )

    result = subprocess.run(
        [resolve_bash_executable(), str(ROOT / "scripts" / "pack.sh")],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    assert "packaging" in result.stderr
    assert args_log.read_text(encoding="utf-8").splitlines() == [
        "-c",
        "import PyInstaller",
    ]


def test_packers_share_one_unique_exclusion_manifest() -> None:
    """Both platform scripts should consume the same non-duplicated module list."""
    manifest = ROOT / "packaging" / "pyinstaller_excludes.txt"
    modules = manifest.read_text(encoding="utf-8").splitlines()

    assert modules
    assert len(modules) == len(set(modules))
    for script in (ROOT / "scripts" / "pack.sh", ROOT / "scripts" / "pack.ps1"):
        text = script.read_text(encoding="utf-8")
        assert "pyinstaller_excludes.txt" in text
        assert "-m pip" not in text
