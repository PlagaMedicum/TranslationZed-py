"""Contracts for layered gate-policy registry and command parity."""

from __future__ import annotations

import json
import re
from pathlib import Path

REQUIRED_LAYER_IDS = ("L0", "L1", "L2", "L3", "L4", "L5", "L6")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _load_registry() -> dict[str, object]:
    path = _repo_root() / "docs" / "reference" / "gate_policy_registry.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _make_targets() -> set[str]:
    makefile = (_repo_root() / "Makefile").read_text(encoding="utf-8")
    targets: set[str] = set()
    pattern = re.compile(r"^([A-Za-z0-9_.-]+):", flags=re.MULTILINE)
    for match in pattern.finditer(makefile):
        targets.add(match.group(1))
    return targets


def test_gate_policy_registry_has_required_layers() -> None:
    """Policy registry should include all normative L0..L6 layers exactly once."""
    payload = _load_registry()
    assert payload.get("version") == 1
    layers = payload.get("layers")
    assert isinstance(layers, list)
    ids = [str(row.get("id")) for row in layers if isinstance(row, dict)]
    assert tuple(ids) == REQUIRED_LAYER_IDS


def test_gate_policy_registry_commands_exist_in_makefile() -> None:
    """All registry gate commands must map to concrete Make targets."""
    payload = _load_registry()
    layers = payload["layers"]
    assert isinstance(layers, list)
    targets = _make_targets()
    for row in layers:
        assert isinstance(row, dict)
        command = row.get("command")
        assert isinstance(command, str) and command.startswith("make ")
        target = command.split()[1]
        assert target in targets


def test_gate_policy_docs_reference_all_registry_commands() -> None:
    """Canonical policy docs must mention each registry gate command."""
    payload = _load_registry()
    layers = payload["layers"]
    assert isinstance(layers, list)
    docs = [
        (_repo_root() / "docs" / "quality" / "testing_strategy.md").read_text(
            encoding="utf-8"
        ),
        (_repo_root() / "docs" / "operations" / "checklists.md").read_text(
            encoding="utf-8"
        ),
        (_repo_root() / "docs" / "reference" / "automation_surface.md").read_text(
            encoding="utf-8"
        ),
    ]
    for row in layers:
        assert isinstance(row, dict)
        command = row.get("command")
        assert isinstance(command, str)
        assert any(command in doc for doc in docs)
