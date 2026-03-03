"""Helpers for resolving a real bash executable across platforms."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


def _candidate_bash_paths() -> list[str]:
    """Return candidate bash executables in priority order."""
    candidates: list[str] = []
    env_bash = os.environ.get("BASH")
    if env_bash:
        candidates.append(env_bash)
    for command in ("bash", "bash.exe"):
        resolved = shutil.which(command)
        if resolved:
            candidates.append(resolved)
    if os.name == "nt":
        candidates.extend(
            [
                r"C:\\Program Files\\Git\\bin\\bash.exe",
                r"C:\\Program Files\\Git\\usr\\bin\\bash.exe",
                r"C:\\msys64\\usr\\bin\\bash.exe",
            ]
        )
    unique: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        normalized = str(Path(candidate))
        key = normalized.lower() if os.name == "nt" else normalized
        if key in seen:
            continue
        seen.add(key)
        unique.append(normalized)
    return unique


def _is_usable_bash(executable: str) -> bool:
    """Return True when executable behaves like a functional bash shell."""
    try:
        probe = subprocess.run(
            [executable, "--version"],
            capture_output=True,
            text=True,
            check=False,
        )
    except (OSError, ValueError):
        return False
    output = f"{probe.stdout}\n{probe.stderr}".lower()
    if "windows subsystem for linux has no installed distributions" in output:
        return False
    if probe.returncode != 0:
        return False
    return "gnu bash" in output or "bash version" in output


def resolve_bash_executable() -> str:
    """Resolve a validated bash executable path for subprocess script tests."""
    for candidate in _candidate_bash_paths():
        if _is_usable_bash(candidate):
            return candidate
    raise RuntimeError("No usable bash executable found for shell-script tests")
