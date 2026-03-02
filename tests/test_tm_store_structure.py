"""Structural regression checks for TMStore refactor maintainability budget."""

from __future__ import annotations

import ast
from pathlib import Path

_TM_STORE_PATH = (
    Path(__file__).resolve().parents[1] / "translationzed_py" / "core" / "tm_store.py"
)
_MAX_TM_STORE_LINES = 1199
_MAX_TM_STORE_FUNCTION_LINES = 179


def _collect_function_lengths(source: str) -> list[tuple[int, str, int, int]]:
    tree = ast.parse(source)
    lengths: list[tuple[int, str, int, int]] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        end = getattr(node, "end_lineno", node.lineno)
        lengths.append((end - node.lineno + 1, node.name, node.lineno, end))
    return sorted(lengths, reverse=True)


def test_tm_store_module_line_budget() -> None:
    """Verify tm_store module stays below line budget after deep refactors."""
    total_lines = len(_TM_STORE_PATH.read_text(encoding="utf-8").splitlines())
    assert total_lines <= _MAX_TM_STORE_LINES


def test_tm_store_longest_function_budget() -> None:
    """Verify tm_store longest function stays below readability threshold."""
    source = _TM_STORE_PATH.read_text(encoding="utf-8")
    lengths = _collect_function_lengths(source)
    assert lengths, "No functions discovered in tm_store.py"
    max_len, name, start, end = lengths[0]
    assert (
        max_len <= _MAX_TM_STORE_FUNCTION_LINES
    ), f"{name} spans {max_len} lines ({start}-{end})"
