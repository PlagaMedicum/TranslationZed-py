from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from translationzed_py.gui import MainWindow
from translationzed_py.gui import main_window as mw


def _make_project(
    tmp_path: Path,
    *,
    locale: str,
    charset: str,
    payload: str,
) -> tuple[Path, Path]:
    root = tmp_path / "proj"
    (root / "EN").mkdir(parents=True, exist_ok=True)
    (root / locale).mkdir(parents=True, exist_ok=True)
    (root / "EN" / "language.txt").write_text(
        "text = English,\ncharset = UTF-8,\n", encoding="utf-8"
    )
    (root / locale / "language.txt").write_text(
        f"text = {locale},\ncharset = {charset},\n", encoding="utf-8"
    )
    (root / "EN" / "ui.txt").write_text('UI_OK = "OK"\n', encoding="utf-8")
    file_path = root / locale / "ui.txt"
    file_path.write_bytes(payload.encode(charset))
    return root, file_path


@pytest.mark.parametrize(
    ("locale", "charset", "payload"),
    [
        ("BE", "UTF-8", 'UI_OK = "Прывітанне"\n'),
        ("BE", "UTF-8", 'UI_OK = "Прывітанне"\r\n'),
        ("RU", "CP1251", 'UI_OK = "Привет"\r\n'),
        ("KO", "UTF-16", 'UI_OK = "테스트"\r\n'),
    ],
)
def test_open_without_edit_does_not_mutate_file_bytes(
    tmp_path: Path,
    qtbot,
    locale: str,
    charset: str,
    payload: str,
) -> None:
    root, file_path = _make_project(
        tmp_path,
        locale=locale,
        charset=charset,
        payload=payload,
    )
    original = file_path.read_bytes()

    win = MainWindow(str(root), selected_locales=[locale])
    qtbot.addWidget(win)
    index = win.fs_model.index_for_path(file_path)
    win._file_chosen(index)

    assert file_path.read_bytes() == original


def test_locale_switch_without_edit_keeps_bytes_for_each_file(
    tmp_path: Path, qtbot
) -> None:
    root = tmp_path / "proj"
    (root / "EN").mkdir(parents=True, exist_ok=True)
    (root / "RU").mkdir(parents=True, exist_ok=True)
    (root / "KO").mkdir(parents=True, exist_ok=True)
    (root / "EN" / "language.txt").write_text(
        "text = English,\ncharset = UTF-8,\n", encoding="utf-8"
    )
    (root / "RU" / "language.txt").write_text(
        "text = Russian,\ncharset = CP1251,\n", encoding="utf-8"
    )
    (root / "KO" / "language.txt").write_text(
        "text = Korean,\ncharset = UTF-16,\n", encoding="utf-8"
    )
    (root / "EN" / "ui.txt").write_text('UI_OK = "OK"\n', encoding="utf-8")
    ru_path = root / "RU" / "ui.txt"
    ko_path = root / "KO" / "ui.txt"
    ru_path.write_bytes('UI_OK = "Привет"\r\n'.encode("cp1251"))
    ko_path.write_bytes('UI_OK = "테스트"\r\n'.encode("utf-16"))
    ru_before = ru_path.read_bytes()
    ko_before = ko_path.read_bytes()

    win = MainWindow(str(root), selected_locales=["RU", "KO"])
    qtbot.addWidget(win)
    ru_index = win.fs_model.index_for_path(ru_path)
    ko_index = win.fs_model.index_for_path(ko_path)
    win._file_chosen(ru_index)
    win._file_chosen(ko_index)

    assert ru_path.read_bytes() == ru_before
    assert ko_path.read_bytes() == ko_before


def test_open_flow_never_calls_original_saver(
    tmp_path: Path, qtbot, monkeypatch
) -> None:
    root, file_path = _make_project(
        tmp_path,
        locale="BE",
        charset="UTF-8",
        payload='UI_OK = "Прывітанне"\n',
    )
    calls = {"save": 0}

    def _fake_save(*_args, **_kwargs):
        calls["save"] += 1
        raise AssertionError("Open flow must not call saver.save")

    monkeypatch.setattr(mw, "save", _fake_save)

    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)
    index = win.fs_model.index_for_path(file_path)
    win._file_chosen(index)

    assert calls["save"] == 0
