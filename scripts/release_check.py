#!/usr/bin/env python3
"""Validate release tag/version/changelog consistency for a release build."""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Any

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


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def run_release_check(*, repo_root: Path, raw_tag: str) -> dict[str, Any]:
    """Return structured release-check summary for the requested tag."""
    expected_version, rc_suffix = _normalize_tag(raw_tag)
    root = repo_root

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

    return {
        "version": 1,
        "tag": raw_tag,
        "normalized_version": expected_version,
        "rc_suffix": rc_suffix,
        "pyproject_version": pyproject_version,
        "module_version": module_version,
        "changelog_has_version": expected_version in changelog_versions,
        "status": "failed" if errors else "passed",
        "errors": errors,
    }


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
    parser.add_argument(
        "--repo-root",
        default="",
        help="Repository root. Defaults to the current repository.",
    )
    parser.add_argument(
        "--json-out",
        default="",
        help="Optional JSON summary output path.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print full structured summary after human-readable output.",
    )
    args = parser.parse_args()

    raw_tag = _resolve_tag(args.tag)
    repo_root = Path(args.repo_root).resolve() if args.repo_root else _repo_root()
    summary = run_release_check(repo_root=repo_root, raw_tag=raw_tag)
    if args.json_out:
        _write_json(Path(args.json_out).resolve(), summary)

    if summary["status"] == "failed":
        print("release-check failed:")
        for item in summary["errors"]:
            print(f"- {item}")
        if args.verbose:
            print(json.dumps(summary, indent=2, sort_keys=True))
        return 1

    suffix = f"-rc{summary['rc_suffix']}" if summary["rc_suffix"] else ""
    print(
        "release-check OK: "
        f"tag={raw_tag} normalized={summary['normalized_version']}{suffix} "
        "(pyproject/version.py/changelog aligned)"
    )
    if args.verbose:
        print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
