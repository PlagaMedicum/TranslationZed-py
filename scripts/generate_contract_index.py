#!/usr/bin/env python3
"""Generate/check machine-readable core contract index for LLM/doc workflows."""

from __future__ import annotations

import argparse
import ast
import json
from dataclasses import dataclass
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


@dataclass(frozen=True)
class SymbolRecord:
    """Serializable symbol contract row."""

    name: str
    kind: str
    lineno: int
    signature: str
    short_context: str
    medium_context: str
    full_context: str
    sections: dict[str, str]


def _first_sentence(text: str) -> str:
    clean = " ".join(text.strip().split())
    if not clean:
        return ""
    for sep in (". ", "? ", "! "):
        idx = clean.find(sep)
        if idx > 0:
            return clean[: idx + 1]
    return clean[:240]


def _extract_sections(doc: str) -> dict[str, str]:
    values = dict.fromkeys(CONTRACT_SECTIONS, "")
    if not doc.strip():
        return values
    lines = doc.splitlines()
    current: str | None = None
    bucket: dict[str, list[str]] = {section: [] for section in CONTRACT_SECTIONS}
    section_set = set(CONTRACT_SECTIONS)
    for raw in lines:
        line = raw.strip()
        if line.endswith(":") and line[:-1] in section_set:
            current = line[:-1]
            continue
        if current is not None:
            if line:
                bucket[current].append(line)
            elif bucket[current]:
                bucket[current].append("")
    for section in CONTRACT_SECTIONS:
        values[section] = "\n".join(bucket[section]).strip()
    return values


def _safe_unparse_signature(node: ast.AST) -> str:
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return ""
    try:
        return ast.unparse(node.args)
    except Exception:
        return ""


def _symbol_from_node(node: ast.AST, *, prefix: str = "") -> SymbolRecord | None:
    if isinstance(node, ast.ClassDef):
        doc = ast.get_docstring(node) or ""
        name = f"{prefix}{node.name}" if prefix else node.name
        return SymbolRecord(
            name=name,
            kind="class",
            lineno=node.lineno,
            signature="",
            short_context=_first_sentence(doc),
            medium_context=doc[:480],
            full_context=doc,
            sections=_extract_sections(doc),
        )
    if isinstance(node, ast.FunctionDef):
        doc = ast.get_docstring(node) or ""
        name = f"{prefix}{node.name}" if prefix else node.name
        return SymbolRecord(
            name=name,
            kind="function",
            lineno=node.lineno,
            signature=_safe_unparse_signature(node),
            short_context=_first_sentence(doc),
            medium_context=doc[:480],
            full_context=doc,
            sections=_extract_sections(doc),
        )
    if isinstance(node, ast.AsyncFunctionDef):
        doc = ast.get_docstring(node) or ""
        name = f"{prefix}{node.name}" if prefix else node.name
        return SymbolRecord(
            name=name,
            kind="async_function",
            lineno=node.lineno,
            signature=_safe_unparse_signature(node),
            short_context=_first_sentence(doc),
            medium_context=doc[:480],
            full_context=doc,
            sections=_extract_sections(doc),
        )
    return None


def _module_records(module_path: Path, repo_root: Path) -> dict[str, Any]:
    source = module_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    module_doc = ast.get_docstring(tree) or ""
    rel = module_path.relative_to(repo_root).as_posix()
    dotted = rel.removesuffix(".py").replace("/", ".")
    symbols: list[SymbolRecord] = []
    for node in tree.body:
        top = _symbol_from_node(node)
        if top is None:
            continue
        symbols.append(top)
        if isinstance(node, ast.ClassDef):
            for child in node.body:
                sub = _symbol_from_node(child, prefix=f"{node.name}.")
                if sub is not None:
                    symbols.append(sub)
    symbols = sorted(symbols, key=lambda item: (item.name, item.lineno))
    return {
        "module": dotted,
        "module_path": rel,
        "short_context": _first_sentence(module_doc),
        "medium_context": module_doc[:480],
        "full_context": module_doc,
        "symbols": [
            {
                "name": row.name,
                "kind": row.kind,
                "lineno": row.lineno,
                "signature": row.signature,
                "short_context": row.short_context,
                "medium_context": row.medium_context,
                "full_context": row.full_context,
                "contracts": row.sections,
            }
            for row in symbols
        ],
    }


def build_contract_index(*, repo_root: Path, scope_dir: Path) -> dict[str, Any]:
    """Build deterministic contract index payload for the configured scope."""
    modules = []
    for module_path in sorted(scope_dir.rglob("*.py")):
        if module_path.name == "__init__.py":
            continue
        modules.append(_module_records(module_path, repo_root))
    return {
        "schema_version": 1,
        "scope": scope_dir.relative_to(repo_root).as_posix(),
        "modules": modules,
    }


def _canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main() -> int:
    """Generate or check the contract index file."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Repository root path",
    )
    parser.add_argument(
        "--scope",
        default="translationzed_py/core",
        help="Python module scope directory for index generation",
    )
    parser.add_argument(
        "--out",
        default="docs/reference/contract_index.json",
        help="Contract index output path",
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="Check output is up to date")
    mode.add_argument("--write", action="store_true", help="Write generated output")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    scope = (repo_root / args.scope).resolve()
    out_path = (repo_root / args.out).resolve()
    payload = build_contract_index(repo_root=repo_root, scope_dir=scope)
    canonical = _canonical_json(payload)

    if args.write:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(canonical, encoding="utf-8")
        print(f"contract-index: wrote {out_path}")
        return 0

    if not out_path.is_file():
        print(f"contract-index: FAIL missing output file: {out_path}")
        print("contract-index: run with --write to bootstrap the artifact")
        return 1
    current = out_path.read_text(encoding="utf-8")
    if current != canonical:
        print("contract-index: FAIL drift detected")
        print(f"contract-index: expected {out_path} to match generated payload")
        print("contract-index: run with --write to refresh committed artifact")
        return 1
    print("contract-index: PASS")
    print(f"validated: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
