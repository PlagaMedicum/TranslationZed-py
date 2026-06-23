#!/usr/bin/env python3
"""Generate compact source-contract context for explicitly selected modules."""

from __future__ import annotations

import argparse
import ast
import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

CONTRACT_SECTIONS = (
    "Preconditions",
    "Postconditions",
    "Invariants",
    "Failure Modes",
    "Side Effects",
    "Determinism",
    "Complexity",
    "Concurrency",
)


def _first_sentence(text: str) -> str:
    clean = " ".join(text.strip().split())
    if not clean:
        return ""
    for separator in (". ", "? ", "! "):
        index = clean.find(separator)
        if index > 0:
            return clean[: index + 1]
    return clean[:240]


def _extract_sections(doc: str) -> dict[str, str]:
    buckets = {name: [] for name in CONTRACT_SECTIONS}
    current: str | None = None
    for raw_line in doc.splitlines():
        line = raw_line.strip()
        heading = line[:-1] if line.endswith(":") else ""
        if heading in buckets:
            current = heading
            continue
        if current and line:
            buckets[current].append(line)
    return {name: "\n".join(lines) for name, lines in buckets.items() if lines}


def _signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    try:
        return ast.unparse(node.args)
    except (AttributeError, ValueError):
        return ""


def _symbol_record(
    node: ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef,
    *,
    prefix: str = "",
) -> dict[str, Any]:
    doc = ast.get_docstring(node) or ""
    name = f"{prefix}{node.name}"
    kind = "class"
    signature = ""
    if isinstance(node, ast.AsyncFunctionDef):
        kind = "async_function"
        signature = _signature(node)
    elif isinstance(node, ast.FunctionDef):
        kind = "function"
        signature = _signature(node)
    return {
        "name": name,
        "kind": kind,
        "lineno": node.lineno,
        "signature": signature,
        "summary": _first_sentence(doc),
        "contracts": _extract_sections(doc),
    }


def _is_public(name: str) -> bool:
    return all(not part.startswith("_") for part in name.split("."))


def _module_record(
    module_path: Path,
    *,
    repo_root: Path,
    public_only: bool,
) -> dict[str, Any]:
    tree = ast.parse(module_path.read_text(encoding="utf-8"), filename=str(module_path))
    relative = module_path.relative_to(repo_root).as_posix()
    symbols: list[dict[str, Any]] = []
    for node in tree.body:
        if not isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        top = _symbol_record(node)
        if not public_only or _is_public(top["name"]):
            symbols.append(top)
        if isinstance(node, ast.ClassDef):
            for child in node.body:
                if not isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                member = _symbol_record(child, prefix=f"{node.name}.")
                if not public_only or _is_public(member["name"]):
                    symbols.append(member)
    return {
        "module": relative.removesuffix(".py").replace("/", "."),
        "module_path": relative,
        "summary": _first_sentence(ast.get_docstring(tree) or ""),
        "symbols": sorted(symbols, key=lambda item: (item["lineno"], item["name"])),
    }


def resolve_module_path(repo_root: Path, value: str) -> Path:
    """Resolve one dotted module or repository-relative Python path."""
    raw = value.strip()
    if not raw:
        raise ValueError("module value must not be empty")
    relative = Path(raw) if raw.endswith(".py") or "/" in raw else Path(*raw.split("."))
    if relative.suffix != ".py":
        relative = relative.with_suffix(".py")
    path = (repo_root / relative).resolve()
    try:
        path.relative_to(repo_root)
    except ValueError as exc:
        raise ValueError(f"module escapes repository root: {value}") from exc
    if not path.is_file():
        raise ValueError(f"module does not exist: {value}")
    return path


def build_contract_index(
    *,
    repo_root: Path,
    module_paths: Iterable[Path],
    public_only: bool = False,
) -> dict[str, Any]:
    """Build deterministic context for selected module paths."""
    unique_paths = sorted({path.resolve() for path in module_paths})
    return {
        "schema_version": 2,
        "modules": [
            _module_record(path, repo_root=repo_root, public_only=public_only)
            for path in unique_paths
        ],
    }


def main() -> int:
    """Run the targeted context generator."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--module",
        action="append",
        required=True,
        help="Dotted module or repository-relative .py path; repeat as needed.",
    )
    parser.add_argument("--repo-root", default=".", help="Repository root.")
    parser.add_argument(
        "--public-only",
        action="store_true",
        help="Exclude private modules, functions, classes, and class members.",
    )
    parser.add_argument(
        "--out",
        default="",
        help="Write JSON to this path instead of stdout.",
    )
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    try:
        module_paths = [resolve_module_path(repo_root, value) for value in args.module]
    except ValueError as exc:
        parser.error(str(exc))
    payload = build_contract_index(
        repo_root=repo_root,
        module_paths=module_paths,
        public_only=args.public_only,
    )
    rendered = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.out:
        output = (repo_root / args.out).resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
        print(f"contract-context: wrote {output}")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
