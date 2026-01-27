import tempfile
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from translationzed_py.core import parse
from translationzed_py.gui.entry_model import TranslationModel


def test_undo_redo(qtbot):
    with tempfile.TemporaryDirectory() as tmpd:
        p = Path(tmpd) / "file.txt"
        p.write_text('HELLO = "Hi"\n', encoding="utf-8")

        pf = parse(p)
        model = TranslationModel(pf)

        # edit value via model ⇒ pushes command
        idx = model.index(0, 1)
        model.setData(idx, "Bonjour")

        assert pf.entries[0].value == "Bonjour"

        model.undo_stack.undo()
        assert pf.entries[0].value == "Hi"

        model.undo_stack.redo()
        assert pf.entries[0].value == "Bonjour"
