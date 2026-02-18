#!/usr/bin/env python3
"""Validate release tag/version/changelog consistency for a release build."""

from __future__ import annotations

import argparse
import os
import re
from pathlib import Path

_TAG_RE = re.compile(r"^(?P<version>\d+\.\d+\.\d+)(?:-rc(?P<rc>\d+))?$", re.IGNORECASE)


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(f"Cannot read {path}: {exc}") from exc


def _extract_pyproject_version(text: str) -> str:
    m = re.search(r'^version\s*=\s*"([^"]+)"\s*$', text, flags=re.MULTILINE)
    if not m:
        raise RuntimeError("Could not find project version in pyproject.toml.")
    return m.group(1).strip()


def _extract_module_version(text: str) -> str:
    m = re.search(r'^__version__\s*=\s*"([^"]+)"\s*$', text, flags=re.MULTILINE)
    if not m:
        raise RuntimeError(
            "Could not find __version__ in translationzed_py/version.py."
        )
    return m.group(1).strip()


def _extract_changelog_versions(text: str) -> set[str]:
    return set(
        re.findall(r"^## \[([0-9]+\.[0-9]+\.[0-9]+)\] - .+$", text, flags=re.MULTILINE)
    )


def _normalize_tag(raw: str) -> tuple[str, str | None]:
    tag = raw.strip()
    if tag.startswith("refs/tags/"):
        tag = tag.removeprefix("refs/tags/")
    if tag.startswith("v"):
        tag = tag[1:]
    match = _TAG_RE.fullmatch(tag)
    if not match:
        raise RuntimeError(f"Tag '{raw}' does not look like vX.Y.Z (or vX.Y.Z-rcN).")
    return match.group("version"), match.group("rc")


def _resolve_tag(cli_tag: str | None) -> str:
    if cli_tag and cli_tag.strip():
        return cli_tag.strip()
    for key in ("TAG", "GITHUB_REF_NAME", "GITHUB_REF"):
        value = os.getenv(key, "").strip()
        if value:
            return value
    raise RuntimeError("No tag provided. Pass --tag vX.Y.Z or set TAG/GITHUB_REF_NAME.")


def main() -> int:
    """Run release metadata checks and return an exit status."""
    parser = argparse.ArgumentParser(
        description="Validate release tag against project versions/changelog."
    )
    parser.add_argument(
        "--tag",
        default="",
        help=(
            "Release tag (for example v0.5.0 or v0.5.0-rc1). "
            "If omitted, TAG/GITHUB_REF_NAME is used."
        ),
    )
    args = parser.parse_args()

    raw_tag = _resolve_tag(args.tag)
    expected_version, rc_suffix = _normalize_tag(raw_tag)
    root = _repo_root()

    pyproject_path = root / "pyproject.toml"
    version_path = root / "translationzed_py" / "version.py"
    changelog_path = root / "CHANGELOG.md"

    pyproject_version = _extract_pyproject_version(_read_text(pyproject_path))
    module_version = _extract_module_version(_read_text(version_path))
    changelog_versions = _extract_changelog_versions(_read_text(changelog_path))

    errors: list[str] = []
    if pyproject_version != expected_version:
        errors.append(
            f"pyproject.toml version is {pyproject_version}, expected {expected_version}."
        )
    if module_version != expected_version:
        errors.append(
            "translationzed_py/version.py __version__ is "
            f"{module_version}, expected {expected_version}."
        )
    if expected_version not in changelog_versions:
        errors.append(
            f"CHANGELOG.md has no section for [{expected_version}] with a release heading."
        )

    if errors:
        print("release-check failed:")
        for item in errors:
            print(f"- {item}")
        return 1

    suffix = f"-rc{rc_suffix}" if rc_suffix else ""
    print(
        "release-check OK: "
        f"tag={raw_tag} normalized={expected_version}{suffix} "
        "(pyproject/version.py/changelog aligned)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
