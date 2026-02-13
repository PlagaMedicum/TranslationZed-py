import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QToolButton

from translationzed_py.gui.dialogs import AboutDialog


def test_about_dialog_has_compact_top_aligned_layout(qtbot) -> None:
    dialog = AboutDialog()
    qtbot.addWidget(dialog)
    layout = dialog.layout()
    assert layout is not None
    assert bool(layout.alignment() & Qt.AlignTop)


def test_about_dialog_license_toggle_does_not_resize_window(qtbot) -> None:
    dialog = AboutDialog()
    qtbot.addWidget(dialog)
    dialog.show()
    qtbot.wait(20)
    initial = dialog.size()

    toggle = None
    for btn in dialog.findChildren(QToolButton):
        if btn.text() == "View License":
            toggle = btn
            break
    assert toggle is not None
    toggle.setChecked(True)
    qtbot.wait(20)
    assert dialog.size() == initial
