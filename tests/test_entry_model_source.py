from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette

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


def test_preview_does_not_affect_edit_role(tmp_path: Path) -> None:
    path = tmp_path / "file.txt"
    path.write_text('HELLO = "Hello world"\n', encoding="utf-8")
    pf = parse(path)
    model = TranslationModel(pf)
    model.set_preview_limit(5)
    idx = model.index(0, 2)
    assert model.data(idx, role=Qt.DisplayRole) == "Hell…"
    assert model.data(idx, role=Qt.EditRole) == "Hello world"


def test_status_background_provides_contrast_foreground(tmp_path: Path) -> None:
    path = tmp_path / "file.txt"
    path.write_text('HELLO = "Hi"\n', encoding="utf-8")
    pf = parse(path)
    object.__setattr__(pf.entries[0], "status", Status.TRANSLATED)
    model = TranslationModel(pf)
    idx = model.index(0, 2)
    bg = model.data(idx, role=Qt.BackgroundRole)
    fg = model.data(idx, role=Qt.ForegroundRole)
    assert bg is not None
    assert fg is not None


def test_dark_palette_uses_dark_status_background(tmp_path: Path, qapp) -> None:
    original_palette = qapp.palette()
    dark_palette = QPalette(original_palette)
    dark_palette.setColor(QPalette.Base, QColor(24, 24, 24))
    dark_palette.setColor(QPalette.Text, QColor(230, 230, 230))
    qapp.setPalette(dark_palette)
    try:
        path = tmp_path / "file.txt"
        path.write_text('HELLO = "Hi"\n', encoding="utf-8")
        pf = parse(path)
        object.__setattr__(pf.entries[0], "status", Status.TRANSLATED)
        model = TranslationModel(pf)
        idx = model.index(0, 2)
        bg = model.data(idx, role=Qt.BackgroundRole)
        fg = model.data(idx, role=Qt.ForegroundRole)
        assert bg is not None
        assert fg is not None
        assert bg.lightness() < 145
        assert fg.lightness() >= 145
    finally:
        qapp.setPalette(original_palette)
