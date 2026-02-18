"""Test module for main-window layout controls and TM helper branches."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtGui import QStandardItemModel

from translationzed_py.gui import MainWindow
from translationzed_py.gui import main_window as mw


def _make_project(tmp_path: Path) -> Path:
    """Create a minimal multi-locale project fixture."""
    root = tmp_path / "proj"
    root.mkdir()
    for locale, text in (
        ("EN", "English"),
        ("BE", "Belarusian"),
        ("RU", "Russian"),
    ):
        (root / locale).mkdir()
        (root / locale / "language.txt").write_text(
            f"text = {text},\ncharset = UTF-8,\n",
            encoding="utf-8",
        )
    (root / "EN" / "ui.txt").write_text('UI_OK = "OK"\n', encoding="utf-8")
    (root / "BE" / "ui.txt").write_text('UI_OK = "Добра"\n', encoding="utf-8")
    (root / "RU" / "ui.txt").write_text('UI_OK = "Хорошо"\n', encoding="utf-8")
    return root


def test_tree_and_detail_panel_toggles_update_layout_hooks(qtbot, tmp_path, monkeypatch) -> None:
    """Verify panel toggles update splitter layout and fire expected hooks."""
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)
    win.show()

    model = QStandardItemModel(1, 1, win.table)
    win.table.setModel(model)
    calls: list[str] = []

    monkeypatch.setattr(win, "_apply_table_layout", lambda: calls.append("layout"))
    monkeypatch.setattr(win, "_schedule_resize_reflow", lambda: calls.append("reflow"))
    monkeypatch.setattr(win, "_sync_detail_editors", lambda: calls.append("sync_detail"))
    monkeypatch.setattr(
        win,
        "_commit_detail_translation",
        lambda *_args, **_kwargs: calls.append("commit_detail"),
    )

    win._content_splitter.setSizes([180, 720])
    win._toggle_tree_panel(True)
    assert win._left_panel.isHidden() is True

    win._toggle_tree_panel(False)
    assert win._left_panel.isHidden() is False
    assert "layout" in calls
    assert "reflow" in calls

    win._detail_last_height = None
    win._toggle_detail_panel(True)
    assert win._detail_panel.isHidden() is False
    assert "sync_detail" in calls

    win._toggle_detail_panel(False)
    assert win._detail_panel.isHidden() is True
    assert "commit_detail" in calls


def test_splitter_move_handlers_persist_sizes_and_schedule_work(qtbot, tmp_path, monkeypatch) -> None:
    """Verify splitter move handlers track widths/heights and schedule persistence."""
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)
    win.show()

    calls: list[str] = []
    monkeypatch.setattr(win, "_schedule_tree_width_persist", lambda: calls.append("persist"))
    monkeypatch.setattr(win, "_schedule_resize_reflow", lambda: calls.append("reflow"))

    win._detail_panel.setVisible(False)
    win._on_main_splitter_moved(0, 0)
    win._detail_panel.setVisible(True)
    win._main_splitter.setSizes([200, 180])
    win._on_main_splitter_moved(0, 0)
    assert win._detail_last_height is not None
    assert win._detail_last_height >= 70

    win.tree.setVisible(False)
    win._on_content_splitter_moved(0, 0)
    win.tree.setVisible(True)
    win._content_splitter.setSizes([240, 480])
    win._on_content_splitter_moved(0, 0)
    assert win._tree_last_width >= 60
    assert calls == ["persist", "reflow"]

    win._tree_width_timer.stop()
    mw.MainWindow._schedule_tree_width_persist(win)
    assert win._tree_width_timer.isActive() is True


def test_tm_helper_methods_cover_path_locale_pairing_and_store_pool(
    qtbot,
    tmp_path,
    monkeypatch,
) -> None:
    """Verify TM helper methods cover normalization, pairing, and pool setup paths."""
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)

    default_tm = win._default_tm_import_dir()
    win._tm_import_dir = "   "
    assert win._tm_import_dir_path() == default_tm

    explicit_tm = root / ".custom_tm"
    win._tm_import_dir = str(explicit_tm)
    assert win._tm_import_dir_path() == explicit_tm.resolve()

    assert win._normalize_tm_locale("") == ""
    assert win._normalize_tm_locale("be") == "BE"
    assert win._normalize_tm_locale("be-extra") == "BE"
    assert win._normalize_tm_locale("xx-extra") == "XX-EXTRA"

    win._tm_source_locale = "EN"
    win._current_pf = type("_PF", (), {"path": root / "BE" / "ui.txt"})()
    auto_pair, skip_all = win._pick_tmx_locales(
        root / "tmx.tmx",
        {"en", "be"},
        interactive=False,
    )
    assert auto_pair == ("EN", "BE")
    assert skip_all is False

    no_pair, skip_all = win._pick_tmx_locales(
        root / "tmx.tmx",
        {"xx"},
        interactive=False,
    )
    assert no_pair is None
    assert skip_all is False

    class _Dialog:
        """TM language dialog stub for accepted and rejected paths."""

        class DialogCode:
            Accepted = 1

        def __init__(self, *_args, **_kwargs):
            self._accept = _kwargs.get("allow_skip_all", False)

        def exec(self) -> int:
            return self.DialogCode.Accepted if self._accept else 0

        def skip_all_requested(self) -> bool:
            return True

        def source_locale(self) -> str:
            return "EN"

        def target_locale(self) -> str:
            return "RU"

    monkeypatch.setattr(mw, "TmLanguageDialog", _Dialog)
    chosen, skip_all = win._pick_tmx_locales(
        root / "tmx.tmx",
        {"ru"},
        interactive=True,
        allow_skip_all=False,
    )
    assert chosen is None
    assert skip_all is True

    chosen, skip_all = win._pick_tmx_locales(
        root / "tmx.tmx",
        {"ru"},
        interactive=True,
        allow_skip_all=True,
    )
    assert chosen == ("EN", "RU")
    assert skip_all is False

    monkeypatch.setattr(win, "_init_tm_store", lambda: None)
    win._tm_store = None
    assert win._ensure_tm_store() is False

    win._tm_store = object()  # type: ignore[assignment]
    win._tm_query_pool = None
    assert win._ensure_tm_store() is True
    assert win._tm_query_pool is not None
