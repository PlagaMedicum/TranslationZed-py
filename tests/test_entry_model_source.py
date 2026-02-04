from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt

from translationzed_py.core import Status, parse
from translationzed_py.gui.entry_model import TranslationModel


def test_source_column(tmp_path: Path) -> None:
    path = tmp_path / "file.txt"
    path.write_text('HELLO = "Hi"\n', encoding="utf-8")
    pf = parse(path)
    model = TranslationModel(pf, source_values={"HELLO": "Hello"})
    idx = model.index(0, 1)
    assert model.data(idx) == "Hello"
    assert not (model.flags(idx) & Qt.ItemIsEditable)


def test_proofread_background(tmp_path: Path) -> None:
    path = tmp_path / "file.txt"
    path.write_text('HELLO = "Hi"\n', encoding="utf-8")
    pf = parse(path)
    # mutate frozen entry for test
    object.__setattr__(pf.entries[0], "status", Status.PROOFREAD)
    model = TranslationModel(pf)
    idx = model.index(0, 3)
    bg = model.data(idx, role=Qt.BackgroundRole)
    assert bg is not None


def test_source_background_uses_by_row(tmp_path: Path) -> None:
    path = tmp_path / "file.txt"
    path.write_text('HELLO = "Hi"\n', encoding="utf-8")
    pf = parse(path)
    model = TranslationModel(pf, source_values={}, source_by_row=["Hello"])
    idx = model.index(0, 1)
    bg = model.data(idx, role=Qt.BackgroundRole)
    assert bg is None


def test_source_background_missing_by_row(tmp_path: Path) -> None:
    path = tmp_path / "file.txt"
    path.write_text('HELLO = "Hi"\n', encoding="utf-8")
    pf = parse(path)
    model = TranslationModel(pf, source_values={}, source_by_row=[""])
    idx = model.index(0, 1)
    bg = model.data(idx, role=Qt.BackgroundRole)
    assert bg is not None
