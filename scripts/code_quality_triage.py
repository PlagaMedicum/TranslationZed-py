#!/usr/bin/env python3
"""Triage changed application modules against the active-risk register."""

from __future__ import annotations

import argparse
import ast
import json
import subprocess
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ModuleStats:
    """Static complexity indicators used for risk discovery."""

    line_count: int
    max_function_lines: int
    max_function_branches: int


def _git_changed_files(repo_root: Path) -> list[str]:
    """Return changed tracked and untracked paths relative to the repository."""
    changed: set[str] = set()
    commands = (
        ("git", "diff", "--name-only", "--relative", "HEAD"),
        ("git", "ls-files", "--others", "--exclude-standard"),
    )
    for command in commands:
        result = subprocess.run(
            command,
            cwd=repo_root,
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            changed.update(line.strip() for line in result.stdout.splitlines() if line)
    return sorted(changed)


def _measure_module(path: Path) -> ModuleStats:
    """Measure size, longest function, and branch density."""
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    max_lines = 0
    max_branches = 0
    branch_nodes = (
        ast.If,
        ast.For,
        ast.AsyncFor,
        ast.While,
        ast.Try,
        ast.BoolOp,
        ast.Match,
        ast.IfExp,
        ast.comprehension,
    )
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        end = getattr(node, "end_lineno", node.lineno)
        max_lines = max(max_lines, end - node.lineno + 1)
        max_branches = max(
            max_branches,
            sum(isinstance(child, branch_nodes) for child in ast.walk(node)),
        )
    return ModuleStats(
        line_count=len(source.splitlines()),
        max_function_lines=max_lines,
        max_function_branches=max_branches,
    )


def _triage_module(path: Path) -> tuple[bool, list[str], ModuleStats]:
    """Return whether a module needs active-risk coverage and why."""
    stats = _measure_module(path)
    reasons: list[str] = []
    if stats.line_count >= 1200:
        reasons.append("module has at least 1200 lines")
    if stats.max_function_lines >= 180:
        reasons.append("function has at least 180 lines")
    if stats.max_function_branches >= 45:
        reasons.append("function has at least 45 branch nodes")
    if path.as_posix().endswith("translationzed_py/gui/main_window.py"):
        reasons.append("module is the primary GUI integration adapter")
    return bool(reasons), reasons, stats


def _load_risks(path: Path) -> dict[str, dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    risks = payload.get("risks", [])
    return {
        row["module_path"]: row
        for row in risks
        if isinstance(row, dict) and isinstance(row.get("module_path"), str)
    }


def _target_modules(repo_root: Path, changed_files: list[str]) -> list[Path]:
    targets: list[Path] = []
    for relative in changed_files:
        if not relative.endswith(".py") or not relative.startswith(
            "translationzed_py/"
        ):
            continue
        path = repo_root / relative
        if path.is_file():
            targets.append(path)
    return sorted(targets)


def run_triage(
    *,
    repo_root: Path,
    risk_register: Path,
    changed_files: list[str] | None = None,
) -> tuple[dict[str, Any], list[str]]:
    """Return a structured report and blocking errors."""
    changed = (
        changed_files if changed_files is not None else _git_changed_files(repo_root)
    )
    risks = _load_risks(risk_register)
    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    for path in _target_modules(repo_root, changed):
        relative = path.relative_to(repo_root).as_posix()
        high_risk, reasons, stats = _triage_module(path)
        registered = risks.get(relative)
        row = {
            "module_path": relative,
            "high_risk": high_risk,
            "reasons": reasons,
            "registered": registered is not None,
            "stats": asdict(stats),
        }
        rows.append(row)
        if high_risk and registered is None:
            errors.append(f"high-risk changed module missing risk entry: {relative}")
        if registered is not None and not registered.get("relevant_tests"):
            errors.append(f"risk entry has no relevant tests: {relative}")
    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "changed_files": changed,
        "modules": rows,
    }
    return report, errors


def main() -> int:
    """Run changed-module triage and write the structured report."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=".")
    parser.add_argument(
        "--risk-register",
        default="docs/reference/risk_register.json",
    )
    parser.add_argument(
        "--out-json",
        default="artifacts/docs/code_triage_report.json",
    )
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    risk_register = (repo_root / args.risk_register).resolve()
    report, errors = run_triage(repo_root=repo_root, risk_register=risk_register)
    output = (repo_root / args.out_json).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if errors:
        print("code-triage: FAIL")
        for error in errors:
            print(f" - {error}")
        return 1
    risky_count = sum(row["high_risk"] for row in report["modules"])
    print(
        f"code-triage: PASS ({len(report['modules'])} changed modules, "
        f"{risky_count} registered high-risk)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
