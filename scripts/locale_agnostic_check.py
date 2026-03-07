#!/usr/bin/env python3
"""Enforce locale-agnostic user-facing copy in production UI/docs paths."""

from __future__ import annotations

import argparse
import ast
import json
import re
from pathlib import Path

ALLOWLIST_MARKER = "locale-agnostic: allow"
GUI_ROOT = Path("translationzed_py/gui")
DOC_PATHS = (
    Path("README.md"),
    Path("docs/reference/quick_context.md"),
    Path("docs/reference/automation_surface.md"),
    Path("docs/reference/test_surface.md"),
    Path("docs/operations/checklists.md"),
    Path("docs/quality/testing_strategy.md"),
    Path("docs/spec/technical.md"),
)

METHOD_SINKS = {
    "addItem",
    "setDetailedText",
    "setInformativeText",
    "setPlaceholderText",
    "setText",
    "setTitle",
    "setToolTip",
    "setWindowTitle",
}
CTOR_SINKS = {
    "QAction",
    "QCheckBox",
    "QGroupBox",
    "QLabel",
    "QMenu",
    "QPushButton",
    "QRadioButton",
}
NON_LOCALE_ABBREVIATIONS = {
    "API",
    "CI",
    "DB",
    "ID",
    "LT",
    "OK",
    "OS",
    "QA",
    "TM",
    "UC",
    "UI",
}

EN_CENTRIC_RULES: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(r"\ben\b\s*,\s*then\s+file\s+locale\b", re.IGNORECASE),
        "EN-centric fallback label is not locale-agnostic",
    ),
    (
        re.compile(r"\bfile\s+locale\s*,\s*then\s+en\b", re.IGNORECASE),
        "EN-centric fallback label is not locale-agnostic",
    ),
    (
        re.compile(r"\bnew\s+in\s+en\b", re.IGNORECASE),
        "EN-centric diff label is not locale-agnostic",
    ),
    (
        re.compile(r"\bmissing\s+in\s+en\b", re.IGNORECASE),
        "EN-centric diff label is not locale-agnostic",
    ),
    (
        re.compile(r"\ben\s+source\s+changed\b", re.IGNORECASE),
        "EN-centric source label is not locale-agnostic",
    ),
)

_LOCALE_TOKEN_RE = re.compile(r"^[A-Za-z]{2,8}(?:-[A-Za-z0-9]{2,8})?$")
_LOCALE_CHAIN_TOKEN_RE = re.compile(r"^[A-Za-z]{2}(?:-[A-Za-z0-9]{2,8})?$")
_CHAIN_MATCH_RE = re.compile(
    r"\b([A-Za-z]{2}(?:-[A-Za-z0-9]{2,8})?"
    r"(?:\s*(?:,|->)\s*[A-Za-z]{2}(?:-[A-Za-z0-9]{2,8})?)+)\b"
)
_JSON_SNIPPET_RE = re.compile(r"\{[^{}]+\}")
_LOCALE_CONTEXT_WORDS = (
    "locale",
    "fallback",
    "source reference",
    "policy",
    "example",
    "e.g.",
    "json",
)


def _literal_text(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        parts: list[str] = []
        for value in node.values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                parts.append(value.value)
            else:
                return None
        return "".join(parts)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _literal_text(node.left)
        right = _literal_text(node.right)
        if left is None or right is None:
            return None
        return left + right
    return None


def _string_from_call(call: ast.Call) -> str | None:
    func = call.func
    sink_name = ""
    is_method = False
    if isinstance(func, ast.Attribute):
        sink_name = func.attr
        is_method = True
    elif isinstance(func, ast.Name):
        sink_name = func.id
    if not sink_name:
        return None
    if is_method and sink_name not in METHOD_SINKS:
        return None
    if not is_method and sink_name not in CTOR_SINKS:
        return None
    if not call.args:
        return None
    return _literal_text(call.args[0])


def _line_allowlisted(lines: list[str], lineno: int) -> bool:
    idx = max(0, lineno - 1)
    candidates = [lines[idx]]
    if idx > 0:
        candidates.append(lines[idx - 1])
    return any(ALLOWLIST_MARKER in candidate for candidate in candidates)


def _locale_chain_violation(text: str) -> str | None:
    lowered = text.lower()
    has_context = any(word in lowered for word in _LOCALE_CONTEXT_WORDS)
    normalized = text.strip().strip("`'\"")
    for match in _CHAIN_MATCH_RE.finditer(text):
        chunk = match.group(1)
        if not has_context and normalized != chunk:
            continue
        raw_tokens = re.split(r"\s*(?:,|->)\s*", chunk)
        tokens = [token.strip().upper() for token in raw_tokens if token.strip()]
        if len(tokens) < 2:
            continue
        if any(not _LOCALE_CHAIN_TOKEN_RE.fullmatch(token) for token in tokens):
            continue
        token_heads = [token.split("-", 1)[0] for token in tokens]
        if all(token in NON_LOCALE_ABBREVIATIONS for token in token_heads):
            continue
        return "concrete locale-code chain example detected"
    return None


def _is_locale_map_payload(payload: object) -> bool:
    if not isinstance(payload, dict) or not payload:
        return False
    for key, value in payload.items():
        if not isinstance(key, str) or not _LOCALE_TOKEN_RE.fullmatch(key.strip()):
            return False
        if isinstance(value, str):
            token = value.strip()
            if _LOCALE_TOKEN_RE.fullmatch(token):
                continue
            if re.fullmatch(r"[a-z]{2,3}(?:-[A-Za-z0-9]{2,8})?", token):
                continue
            return False
        elif isinstance(value, list):
            if not value:
                return False
            for item in value:
                if not isinstance(item, str) or not _LOCALE_TOKEN_RE.fullmatch(
                    item.strip()
                ):
                    return False
        else:
            return False
    return True


def _locale_json_violation(text: str) -> str | None:
    for snippet_match in _JSON_SNIPPET_RE.finditer(text):
        snippet = snippet_match.group(0)
        try:
            parsed = json.loads(snippet)
        except json.JSONDecodeError:
            continue
        if _is_locale_map_payload(parsed):
            return "concrete locale JSON example detected"
    return None


def _en_centric_violation(text: str) -> str | None:
    for pattern, reason in EN_CENTRIC_RULES:
        if pattern.search(text):
            return reason
    return None


def _string_violations(text: str) -> list[str]:
    checks = (_en_centric_violation, _locale_json_violation, _locale_chain_violation)
    issues: list[str] = []
    for check in checks:
        result = check(text)
        if result:
            issues.append(result)
    return issues


def _iter_gui_strings(path: Path, text: str) -> list[tuple[int, str]]:
    tree = ast.parse(text)
    rows: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        value = _string_from_call(node)
        if not value:
            continue
        rows.append((int(getattr(node, "lineno", 1)), value))
    return rows


def _scan_gui_code(repo_root: Path) -> list[str]:
    errors: list[str] = []
    root = repo_root / GUI_ROOT
    if not root.is_dir():
        return errors
    for path in sorted(root.rglob("*.py")):
        rel = path.relative_to(repo_root).as_posix()
        if "/tests/" in rel or "/fixtures/" in rel:
            continue
        text = path.read_text(encoding="utf-8")
        lines = text.splitlines()
        for lineno, value in _iter_gui_strings(path, text):
            if _line_allowlisted(lines, lineno):
                continue
            violations = _string_violations(value)
            for issue in violations:
                errors.append(f"{rel}:{lineno}: {issue}: {value!r}")
    return errors


def _scan_docs(repo_root: Path) -> list[str]:
    errors: list[str] = []
    for rel_path in DOC_PATHS:
        path = repo_root / rel_path
        if not path.is_file():
            continue
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if ALLOWLIST_MARKER in line:
                continue
            violations = _string_violations(line)
            for issue in violations:
                errors.append(
                    f"{rel_path.as_posix()}:{lineno}: {issue}: {line.strip()!r}"
                )
    return errors


def validate_locale_agnostic_contract(repo_root: Path) -> list[str]:
    """Validate locale-agnostic user-facing copy across production paths."""
    errors = []
    errors.extend(_scan_gui_code(repo_root))
    errors.extend(_scan_docs(repo_root))
    return sorted(errors)


def main() -> int:
    """Run locale-agnostic copy validation CLI."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Repository root path.",
    )
    args = parser.parse_args()
    repo_root = Path(args.repo_root).resolve()
    errors = validate_locale_agnostic_contract(repo_root)
    if errors:
        print("locale-agnostic-check: FAIL")
        for error in errors:
            print(f" - {error}")
        return 1
    print("locale-agnostic-check: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
