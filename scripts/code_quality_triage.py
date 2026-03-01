#!/usr/bin/env python3
"""Run touched-module Document-or-Flag triage and emit trace artifacts."""

from __future__ import annotations

import argparse
import ast
import json
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ACTIVE_REVIEW_STATUSES = {"REVIEW_REQUIRED", "IN_REFACTOR"}
TRIAGE_RULE_IDS = (
    "ARCH_BOUNDARY",
    "STATE_INCOHERENCE",
    "TEST_GAP",
    "COMPLEXITY",
    "DOC_DRIFT",
)
TRIAGE_DEEP_DOC_PATHS = {
    "docs/architecture/code_architecture.md",
    "docs/architecture/flows.md",
    "docs/spec/technical.md",
    "docs/reference/module_map.md",
}
TRIAGE_DEEP_DOC_PREFIXES = (
    "docs/reference/api/",
)
MODULE_DIRECTIVE_PATTERN = ":::"
FLAGGED_MODULE_PATTERN = "FLAGGED_MODULE:"
TRIAGE_MODULE_PATTERN = "TRIAGE_MODULE:"
DOC_REFERENCE_PATHS = (
    "docs/architecture/code_architecture.md",
    "docs/architecture/flows.md",
    "docs/spec/technical.md",
    "docs/reference/module_map.md",
)


@dataclass(frozen=True)
class ModuleStats:
    """Static complexity snapshot for one module file."""

    line_count: int
    max_function_lines: int
    max_function_branches: int


def _git_changed_files(repo_root: Path) -> list[str]:
    """Return repo-relative changed file paths (working tree + last commit fallback)."""
    changed: set[str] = set()
    commands = [
        ["git", "diff", "--name-only", "--relative", "HEAD"],
        ["git", "diff", "--name-only", "--relative", "HEAD~1", "HEAD"],
        ["git", "ls-files", "--others", "--exclude-standard"],
    ]
    for cmd in commands:
        try:
            proc = subprocess.run(
                cmd,
                cwd=repo_root,
                check=False,
                capture_output=True,
                text=True,
            )
        except OSError:
            continue
        if proc.returncode != 0:
            continue
        for line in proc.stdout.splitlines():
            rel = line.strip()
            if rel:
                changed.add(rel)
    return sorted(changed)


def _extract_modules_from_doc(path: Path) -> set[str]:
    """Extract explicitly-marked dotted module names from a deep-doc markdown file."""
    text = path.read_text(encoding="utf-8")
    modules: set[str] = set()

    def _normalize(raw: str) -> str | None:
        token = raw.strip().strip("`*[](){}<>.,:;")
        if not token:
            return None
        if token.startswith("translationzed_py/") and token.endswith(".py"):
            return token.removesuffix(".py").replace("/", ".")
        if token.startswith("translationzed_py."):
            if token.replace(".", "").replace("_", "").isalnum():
                return token
        return None

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line.startswith(MODULE_DIRECTIVE_PATTERN):
            payload = line.removeprefix(MODULE_DIRECTIVE_PATTERN).strip()
            if payload:
                normalized = _normalize(payload.split()[0])
                if normalized:
                    modules.add(normalized)
        if FLAGGED_MODULE_PATTERN in line:
            payload = line.split(FLAGGED_MODULE_PATTERN, 1)[1].strip()
            if payload:
                normalized = _normalize(payload.split()[0])
                if normalized:
                    modules.add(normalized)
        if TRIAGE_MODULE_PATTERN in line:
            payload = line.split(TRIAGE_MODULE_PATTERN, 1)[1].strip()
            if payload:
                normalized = _normalize(payload.split()[0])
                if normalized:
                    modules.add(normalized)
    return modules


def _module_to_path(repo_root: Path, dotted: str) -> Path:
    """Translate dotted module name into filesystem path."""
    return repo_root / (dotted.replace(".", "/") + ".py")


def _measure_module(path: Path) -> ModuleStats:
    """Collect deterministic static complexity counters for one module file."""
    source = path.read_text(encoding="utf-8")
    line_count = len(source.splitlines())
    tree = ast.parse(source)
    max_fn_lines = 0
    max_fn_branches = 0
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if getattr(node, "end_lineno", None):
                max_fn_lines = max(max_fn_lines, node.end_lineno - node.lineno + 1)
            branches = 0
            for child in ast.walk(node):
                if isinstance(
                    child,
                    (
                        ast.If,
                        ast.For,
                        ast.AsyncFor,
                        ast.While,
                        ast.Try,
                        ast.BoolOp,
                        ast.Match,
                        ast.IfExp,
                        ast.comprehension,
                    ),
                ):
                    branches += 1
            max_fn_branches = max(max_fn_branches, branches)
    return ModuleStats(
        line_count=line_count,
        max_function_lines=max_fn_lines,
        max_function_branches=max_fn_branches,
    )


def _load_doc_reference_blob(repo_root: Path) -> str:
    """Return concatenated canonical doc text used for DOC_DRIFT heuristic."""
    chunks: list[str] = []
    for rel in DOC_REFERENCE_PATHS:
        path = repo_root / rel
        if path.is_file():
            chunks.append(path.read_text(encoding="utf-8"))
    return "\n".join(chunks)


def _load_test_inventory(repo_root: Path) -> tuple[tuple[Path, ...], str]:
    """Collect test files and concatenated source text for TEST_GAP heuristics."""
    tests_root = repo_root / "tests"
    if not tests_root.is_dir():
        return (), ""
    files = tuple(sorted(tests_root.rglob("test_*.py")))
    chunks: list[str] = []
    for path in files:
        chunks.append(path.as_posix())
        try:
            chunks.append(path.read_text(encoding="utf-8"))
        except OSError:
            continue
    return files, "\n".join(chunks)


def _has_test_coverage(
    *,
    module_dotted: str,
    module_rel: str,
    test_files: tuple[Path, ...],
    test_blob: str,
) -> bool:
    """Return True when module has direct or name-based test references."""
    stem = Path(module_rel).stem
    if any(stem in path.name for path in test_files):
        return True
    patterns = (
        module_dotted,
        module_rel,
        f"import {module_dotted}",
        f"from {module_dotted} import",
    )
    return any(pattern in test_blob for pattern in patterns)


def _has_doc_reference(module_dotted: str, module_rel: str, doc_blob: str) -> bool:
    """Return True when module appears in canonical architecture/spec references."""
    return module_dotted in doc_blob or module_rel in doc_blob


def _load_active_queue_entries(path: Path) -> dict[str, dict[str, Any]]:
    """Load active queue entries keyed by module path."""
    if not path.is_file():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    entries = payload.get("entries", [])
    active: dict[str, dict[str, Any]] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        module_path = entry.get("module_path")
        status = entry.get("status")
        if (
            isinstance(module_path, str)
            and isinstance(status, str)
            and status in ACTIVE_REVIEW_STATUSES
        ):
            active[module_path] = entry
    return active


def _triage_module(module_path: Path) -> tuple[str, str, list[str], list[str]]:
    """Return (outcome, risk, reason_codes, evidence)."""
    evidence: list[str] = []
    reasons: list[str] = []
    if not module_path.is_file():
        return (
            "REVIEW_REQUIRED",
            "P0",
            ["DOC_DRIFT"],
            ["Referenced module path does not exist on disk."],
        )
    stats = _measure_module(module_path)
    evidence.append(f"line_count={stats.line_count}")
    evidence.append(f"max_function_lines={stats.max_function_lines}")
    evidence.append(f"max_function_branches={stats.max_function_branches}")

    risk = "P2"
    if stats.line_count >= 1200:
        reasons.append("COMPLEXITY")
        risk = "P1"
    if stats.max_function_lines >= 180:
        reasons.append("COMPLEXITY")
        risk = "P1"
    if stats.max_function_branches >= 45:
        reasons.append("STATE_INCOHERENCE")
        risk = "P1"
    if module_path.as_posix().endswith("gui/main_window.py"):
        reasons.append("ARCH_BOUNDARY")
        risk = "P0"

    reasons = sorted(set(reasons))
    if reasons:
        return ("REVIEW_REQUIRED", risk, reasons, evidence)
    return ("PASS", risk, [], evidence)


def _is_deep_doc(path: str) -> bool:
    if path in TRIAGE_DEEP_DOC_PATHS:
        return True
    return any(path.startswith(prefix) for prefix in TRIAGE_DEEP_DOC_PREFIXES)


def _path_to_dotted(path: str) -> str:
    """Convert repo-relative python path to dotted module name."""
    return path.removesuffix(".py").replace("/", ".")


def _collect_target_modules(
    repo_root: Path, changed_files: list[str], manual_modules: list[str]
) -> tuple[set[str], list[str]]:
    modules = {m.strip() for m in manual_modules if m.strip()}

    changed_core_modules = {
        _path_to_dotted(path)
        for path in changed_files
        if path.startswith("translationzed_py/core/") and path.endswith(".py")
    }
    modules.update(changed_core_modules)

    deep_doc_files = [path for path in changed_files if _is_deep_doc(path)]
    docs_modules: set[str] = set()
    for rel in deep_doc_files:
        doc_path = repo_root / rel
        if doc_path.is_file():
            docs_modules.update(_extract_modules_from_doc(doc_path))
    modules.update(
        module for module in docs_modules if module.startswith("translationzed_py.core.")
    )
    return modules, deep_doc_files


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    """Execute triage flow and return process exit code."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Repository root path (default: current directory)",
    )
    parser.add_argument(
        "--review-queue",
        default="docs/reference/review_queue.json",
        help="Path to review queue JSON artifact",
    )
    parser.add_argument(
        "--out-json",
        default="artifacts/docs/code_triage_report.json",
        help="Path for full triage report JSON",
    )
    parser.add_argument(
        "--pass-log",
        default="artifacts/docs/triage_pass_log.json",
        help="Path for PASS-only trace artifact",
    )
    parser.add_argument(
        "--module",
        action="append",
        default=[],
        help="Explicit dotted module to triage (repeatable)",
    )
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    review_queue_path = (repo_root / args.review_queue).resolve()
    out_json = (repo_root / args.out_json).resolve()
    pass_log = (repo_root / args.pass_log).resolve()
    changed_files = _git_changed_files(repo_root)
    modules, deep_doc_files = _collect_target_modules(repo_root, changed_files, args.module)
    test_files, test_blob = _load_test_inventory(repo_root)
    doc_blob = _load_doc_reference_blob(repo_root)

    active_queue = _load_active_queue_entries(review_queue_path)
    report_rows: list[dict[str, Any]] = []
    missing_queue: list[str] = []
    pass_rows: list[dict[str, Any]] = []

    for module in sorted(modules):
        module_file = _module_to_path(repo_root, module)
        outcome, risk_level, reason_codes, evidence = _triage_module(module_file)
        module_rel = module_file.relative_to(repo_root).as_posix()
        stats = _measure_module(module_file) if module_file.is_file() else None
        test_gap_candidate = bool(reason_codes) and stats is not None
        if test_gap_candidate and not _has_test_coverage(
            module_dotted=module,
            module_rel=module_rel,
            test_files=test_files,
            test_blob=test_blob,
        ):
            reason_codes.append("TEST_GAP")
            evidence.append("No direct module reference found in tests inventory.")
            outcome = "REVIEW_REQUIRED"
            if risk_level != "P0":
                risk_level = "P1"
        if not _has_doc_reference(module, module_rel, doc_blob):
            evidence.append(
                "Module missing from canonical architecture/spec/module-map references."
            )
            if outcome == "REVIEW_REQUIRED":
                reason_codes.append("DOC_DRIFT")
        reason_codes = sorted(set(reason_codes))
        row = {
            "module": module,
            "module_path": module_rel,
            "outcome": outcome,
            "risk_level": risk_level,
            "reason_codes": reason_codes,
            "evidence": evidence,
        }
        report_rows.append(row)
        if outcome == "PASS":
            pass_rows.append(row)
            continue
        if module_rel not in active_queue:
            missing_queue.append(module_rel)

    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "changed_files": changed_files,
        "deep_doc_files": deep_doc_files,
        "triage_rules": TRIAGE_RULE_IDS,
        "modules": report_rows,
        "missing_queue_entries": sorted(missing_queue),
    }
    pass_payload = {
        "generated_at": report["generated_at"],
        "modules": pass_rows,
    }
    _write_json(out_json, report)
    _write_json(pass_log, pass_payload)

    if missing_queue:
        print("code-triage: FAIL")
        for module_rel in missing_queue:
            print(
                f" - REVIEW_REQUIRED module missing active queue entry: {module_rel} "
                f"(docs/reference/review_queue.json)"
            )
        return 1

    print("code-triage: PASS")
    print(f"triaged modules: {len(report_rows)}")
    print(f"report: {out_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
