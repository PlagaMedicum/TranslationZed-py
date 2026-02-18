"""Test module for filesystem tree model helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QModelIndex

from translationzed_py.core.project_scanner import LocaleMeta
from translationzed_py.gui.fs_model import FsModel


def _locale_meta(root: Path, code: str) -> LocaleMeta:
    """Build locale metadata for tests."""
    locale_path = root / code
    locale_path.mkdir(parents=True, exist_ok=True)
    return LocaleMeta(code=code, path=locale_path, display_name=code, charset="UTF-8")


def test_lazy_model_loads_locale_on_index_and_applies_pending_dirty(
    tmp_path, monkeypatch
) -> None:
    """Verify lazy locale loading and pending-dirty marker application."""
    root = tmp_path / "project"
    root.mkdir()
    meta = _locale_meta(root, "BE")
    target_file = meta.path / "ui.txt"

    monkeypatch.setattr(
        "translationzed_py.gui.fs_model.list_translatable_files",
        lambda _path: [target_file],
    )

    model = FsModel(root, [meta], lazy=True)

    assert model.is_lazy() is True
    model.set_dirty(target_file, True)
    assert str(target_file) in model._pending_dirty

    locale_index = model.index(0, 0)
    model.ensure_loaded_for_index(locale_index)
    loaded_index = model.index_for_path(target_file)

    assert loaded_index.isValid() is True
    item = model.itemFromIndex(loaded_index)
    assert item is not None
    assert item.text().startswith("● ")
    assert str(target_file) not in model._pending_dirty


def test_ensure_loaded_handles_invalid_index_and_missing_item(
    tmp_path, monkeypatch
) -> None:
    """Verify ensure-loaded exits safely for invalid indexes and missing items."""
    root = tmp_path / "project"
    root.mkdir()
    meta = _locale_meta(root, "BE")
    monkeypatch.setattr(
        "translationzed_py.gui.fs_model.list_translatable_files",
        lambda _path: [],
    )
    model = FsModel(root, [meta], lazy=True)

    model.ensure_loaded_for_index(QModelIndex())

    valid_index = model.index(0, 0)
    monkeypatch.setattr(model, "itemFromIndex", lambda _index: None)
    model.ensure_loaded_for_index(valid_index)
    model._ensure_locale_loaded("RU")


def test_set_dirty_tracks_unknown_paths_and_undirty_clears_pending(
    tmp_path, monkeypatch
) -> None:
    """Verify unknown-path dirty state is tracked then removable."""
    root = tmp_path / "project"
    root.mkdir()
    meta = _locale_meta(root, "BE")
    monkeypatch.setattr(
        "translationzed_py.gui.fs_model.list_translatable_files",
        lambda _path: [],
    )
    model = FsModel(root, [meta], lazy=True)
    unknown = root / "BE" / "unknown.txt"

    model.set_dirty(unknown, True)
    assert str(unknown) in model._pending_dirty

    model.set_dirty(unknown, False)
    assert str(unknown) not in model._pending_dirty


def test_index_for_path_returns_invalid_when_not_found(tmp_path, monkeypatch) -> None:
    """Verify index resolution returns invalid index for unknown files."""
    root = tmp_path / "project"
    root.mkdir()
    meta = _locale_meta(root, "BE")
    missing = root / "BE" / "missing.txt"

    monkeypatch.setattr(
        "translationzed_py.gui.fs_model.list_translatable_files",
        lambda _path: [],
    )
    non_lazy_model = FsModel(root, [meta], lazy=False)
    assert non_lazy_model.index_for_path(missing).isValid() is False

    lazy_model = FsModel(root, [meta], lazy=True)
    assert lazy_model.index_for_path(missing).isValid() is False
    assert lazy_model._locale_code_for_path(root) is None
    assert lazy_model._locale_code_for_path(Path("/outside/project/BE/ui.txt")) is None
