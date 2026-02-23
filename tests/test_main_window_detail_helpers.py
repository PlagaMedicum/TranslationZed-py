"""Test module for main-window detail editor helper branches."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt

from translationzed_py.core.languagetool import (
    LT_LEVEL_DEFAULT,
    LT_STATUS_OK,
    LanguageToolCheckResult,
    LanguageToolMatch,
)
from translationzed_py.gui import MainWindow
from translationzed_py.gui import main_window as mw


def _make_project(tmp_path: Path) -> Path:
    """Create a minimal two-locale project for detail-editor tests."""
    root = tmp_path / "proj"
    root.mkdir()
    for locale, text in (
        ("EN", "English"),
        ("BE", "Belarusian"),
    ):
        (root / locale).mkdir()
        (root / locale / "language.txt").write_text(
            f"text = {text},\ncharset = UTF-8,\n",
            encoding="utf-8",
        )
    (root / "EN" / "ui.txt").write_text('UI_OK = "OK"\n', encoding="utf-8")
    (root / "BE" / "ui.txt").write_text('UI_OK = "Добра"\n', encoding="utf-8")
    return root


def _open_window_with_current_file(qtbot, tmp_path: Path) -> tuple[MainWindow, Path]:
    """Return an initialized main window with the current file selected."""
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)
    win.show()
    index = win.fs_model.index_for_path(root / "BE" / "ui.txt")
    win._file_chosen(index)
    win._detail_panel.setVisible(True)
    model = win.table.model()
    assert model is not None
    win.table.setCurrentIndex(model.index(0, 2))
    return win, root


def test_load_pending_detail_text_covers_guards_and_success(
    qtbot,
    tmp_path,
    monkeypatch,
) -> None:
    """Verify pending-detail loader handles guard clauses and normal load."""
    win, _root = _open_window_with_current_file(qtbot, tmp_path)
    assert win._current_model is not None
    model = win.table.model()
    assert model is not None

    win._detail_source.setPlainText("source-sentinel")
    win._detail_translation.setPlainText("value-sentinel")
    win._detail_pending_row = None
    win._detail_pending_active = False
    win._load_pending_detail_text()
    assert win._detail_source.toPlainText() == "source-sentinel"
    assert win._detail_translation.toPlainText() == "value-sentinel"

    win._detail_pending_row = 0
    win._detail_pending_active = True

    win._detail_panel.setVisible(False)
    win._load_pending_detail_text()
    assert win._detail_pending_row == 0
    assert win._detail_pending_active is True

    win._detail_panel.setVisible(True)
    saved_model = win._current_model
    win._current_model = None
    win._load_pending_detail_text()
    assert win._detail_pending_row == 0
    assert win._detail_pending_active is True
    win._current_model = saved_model

    monkeypatch.setattr(win.table, "currentIndex", lambda: model.index(-1, -1))
    win._load_pending_detail_text()
    assert win._detail_pending_row == 0
    assert win._detail_pending_active is True

    monkeypatch.setattr(win.table, "currentIndex", lambda: model.index(0, 2))
    win.table.setCurrentIndex(model.index(0, 2))
    expected_source = str(win._current_model.index(0, 1).data(Qt.EditRole) or "")
    expected_value = str(win._current_model.index(0, 2).data(Qt.EditRole) or "")
    win._detail_translation.setReadOnly(True)
    win._detail_source.setPlaceholderText("pending-source")
    win._detail_translation.setPlaceholderText("pending-value")
    win._detail_source.setPlainText("")
    win._detail_translation.setPlainText("")
    win._load_pending_detail_text()

    assert win._detail_source.toPlainText() == expected_source
    assert win._detail_translation.toPlainText() == expected_value
    assert win._detail_translation.isReadOnly() is False
    assert win._detail_source.placeholderText() == ""
    assert win._detail_translation.placeholderText() == ""
    assert win._detail_pending_row is None
    assert win._detail_pending_active is False
    assert win._detail_dirty is False


def test_set_detail_pending_covers_model_and_no_model_paths(
    qtbot,
    tmp_path,
    monkeypatch,
) -> None:
    """Verify set-detail-pending captures lengths, placeholders, and focus trigger."""
    win, _root = _open_window_with_current_file(qtbot, tmp_path)

    char_calls: list[tuple[int | None, int | None]] = []
    load_calls: list[str] = []
    monkeypatch.setattr(
        win, "_set_detail_char_counts", lambda s, t: char_calls.append((s, t))
    )
    monkeypatch.setattr(
        win, "_load_pending_detail_text", lambda: load_calls.append("load")
    )
    monkeypatch.setattr(win._detail_source, "hasFocus", lambda: False, raising=False)
    monkeypatch.setattr(
        win._detail_translation, "hasFocus", lambda: False, raising=False
    )

    win._set_detail_pending(0)
    assert win._detail_pending_row == 0
    assert win._detail_pending_active is True
    assert win._detail_syncing is False
    assert win._detail_dirty is False
    assert win._detail_translation.isReadOnly() is True
    assert (
        win._detail_source.placeholderText() == "Large text. Click to load full source."
    )
    assert (
        win._detail_translation.placeholderText()
        == "Large text. Click to load full translation."
    )
    assert win._detail_source.toPlainText() == ""
    assert win._detail_translation.toPlainText() == ""
    assert load_calls == []
    assert char_calls[-1][0] is not None
    assert char_calls[-1][1] is not None

    monkeypatch.setattr(win._detail_source, "hasFocus", lambda: True, raising=False)
    win._set_detail_pending(0)
    assert load_calls == ["load"]

    win._current_model = None
    monkeypatch.setattr(win._detail_source, "hasFocus", lambda: False, raising=False)
    monkeypatch.setattr(
        win._detail_translation, "hasFocus", lambda: False, raising=False
    )
    win._set_detail_pending(0)
    assert char_calls[-1] == (None, None)


def test_commit_detail_translation_covers_pending_and_invalid_index_paths(
    qtbot,
    tmp_path,
    monkeypatch,
) -> None:
    """Verify commit-detail exits for pending rows and clears dirty on invalid index."""
    win, _root = _open_window_with_current_file(qtbot, tmp_path)
    assert win._current_model is not None

    win._detail_dirty = True
    win._detail_pending_row = 0
    win._commit_detail_translation()
    assert win._detail_dirty is True

    model = win.table.model()
    assert model is not None
    win._detail_pending_row = None
    win._detail_dirty = True
    monkeypatch.setattr(win.table, "currentIndex", lambda: model.index(-1, -1))
    win._commit_detail_translation()
    assert win._detail_dirty is False


def test_sync_detail_editors_uses_pending_mode_for_large_rows(
    qtbot,
    tmp_path,
    monkeypatch,
) -> None:
    """Verify sync-detail delegates to pending-mode when lazy threshold is reached."""
    win, _root = _open_window_with_current_file(qtbot, tmp_path)
    assert win._current_model is not None
    win._large_text_optimizations = True

    pending_calls: list[int] = []
    monkeypatch.setattr(mw, "_DETAIL_LAZY_THRESHOLD", 1)
    monkeypatch.setattr(
        win, "_set_detail_pending", lambda row: pending_calls.append(row)
    )

    win._sync_detail_editors()
    assert pending_calls == [0]


class _DoneFuture:
    """Small done future stub for LT editor poll tests."""

    def __init__(self, payload) -> None:  # type: ignore[no-untyped-def]
        self._payload = payload

    def done(self) -> bool:
        return True

    def result(self):  # type: ignore[no-untyped-def]
        return self._payload


def test_languagetool_editor_applies_status_and_underlines(
    qtbot,
    tmp_path,
) -> None:
    """Verify LT editor applies underline selections and status transitions."""
    win, _root = _open_window_with_current_file(qtbot, tmp_path)
    win._lt_editor_mode = "on"

    issue_result = LanguageToolCheckResult(
        status=LT_STATUS_OK,
        matches=(
            LanguageToolMatch(
                offset=0,
                length=2,
                message="Issue",
                replacements=(),
                rule_id="R1",
                category_id="GRAMMAR",
                issue_type="grammar",
            ),
        ),
        used_level=LT_LEVEL_DEFAULT,
        fallback_used=False,
        warning="",
        error="",
    )
    win._apply_languagetool_editor_result(issue_result)
    assert win._detail_lt_status_label.text() == "LT: issues:1"
    assert len(win._detail_translation.extraSelections()) == 1

    ok_result = LanguageToolCheckResult(
        status=LT_STATUS_OK,
        matches=(),
        used_level=LT_LEVEL_DEFAULT,
        fallback_used=False,
        warning="",
        error="",
    )
    win._apply_languagetool_editor_result(ok_result)
    assert win._detail_lt_status_label.text() == "LT: ok"
    assert win._detail_translation.extraSelections() == []

    fallback_result = LanguageToolCheckResult(
        status=LT_STATUS_OK,
        matches=(),
        used_level=LT_LEVEL_DEFAULT,
        fallback_used=True,
        warning="Picky unsupported by server; using default level.",
        error="",
    )
    win._apply_languagetool_editor_result(fallback_result)
    assert win._detail_lt_status_label.text() == "LT: picky unsupported (default used)"


def test_languagetool_editor_schedule_uses_latest_pending_payload(
    qtbot,
    tmp_path,
) -> None:
    """Verify LT editor debounced scheduling keeps only latest payload state."""
    win, _root = _open_window_with_current_file(qtbot, tmp_path)
    win._lt_editor_mode = "on"
    win._detail_translation.setPlainText("first")
    win._schedule_languagetool_editor_check()
    first_pending = win._lt_pending_payload
    assert first_pending is not None

    win._detail_translation.setPlainText("second")
    win._schedule_languagetool_editor_check()
    second_pending = win._lt_pending_payload
    assert second_pending is not None
    assert second_pending[0] > first_pending[0]
    assert second_pending[3] == "second"


def test_languagetool_editor_poll_ignores_stale_results(
    qtbot,
    tmp_path,
) -> None:
    """Verify LT editor poll discards stale async results for old text."""
    win, _root = _open_window_with_current_file(qtbot, tmp_path)
    win._lt_editor_mode = "on"
    current_path = win._current_pf.path
    win._detail_translation.setPlainText("new text")
    win._lt_pending_payload = None
    if win._lt_debounce_timer.isActive():
        win._lt_debounce_timer.stop()
    win._detail_lt_status_label.setText("LT: idle")

    stale_result = LanguageToolCheckResult(
        status=LT_STATUS_OK,
        matches=(
            LanguageToolMatch(
                offset=0,
                length=3,
                message="Old issue",
                replacements=(),
                rule_id="R1",
                category_id="GRAMMAR",
                issue_type="grammar",
            ),
        ),
        used_level=LT_LEVEL_DEFAULT,
        fallback_used=False,
        warning="",
        error="",
    )
    win._lt_scan_future = _DoneFuture((1, current_path, 0, "old text", stale_result))
    win._poll_languagetool_editor_check()
    assert win._detail_lt_status_label.text() == "LT: idle"
    assert win._detail_translation.extraSelections() == []


def test_languagetool_hint_popup_only_shows_for_issue_positions(
    qtbot,
    tmp_path,
) -> None:
    """Verify LT hint popup opens only when clicked position has an LT issue."""
    win, _root = _open_window_with_current_file(qtbot, tmp_path)
    win._detail_translation.setPlainText("teh value")
    win._lt_editor_mode = "on"
    result = LanguageToolCheckResult(
        status=LT_STATUS_OK,
        matches=(
            LanguageToolMatch(
                offset=0,
                length=3,
                message="Possible typo",
                replacements=("the", "tech"),
                rule_id="MORFOLOGIK_RULE_EN_US",
                category_id="TYPOS",
                issue_type="misspelling",
            ),
        ),
        used_level=LT_LEVEL_DEFAULT,
        fallback_used=False,
        warning="",
        error="",
    )
    win._apply_languagetool_editor_result(result)
    assert win._show_languagetool_hint_for_position(0) is True
    assert win._lt_hint_menu is not None
    assert win._show_languagetool_hint_for_position(7) is False


def test_languagetool_hint_replacement_updates_text_and_rechecks(
    qtbot,
    tmp_path,
    monkeypatch,
) -> None:
    """Verify LT hint replacement mutates editor text and triggers immediate re-check."""
    win, _root = _open_window_with_current_file(qtbot, tmp_path)
    win._detail_translation.setPlainText("teh value")
    result = LanguageToolCheckResult(
        status=LT_STATUS_OK,
        matches=(
            LanguageToolMatch(
                offset=0,
                length=3,
                message="Possible typo",
                replacements=("the",),
                rule_id="MORFOLOGIK_RULE_EN_US",
                category_id="TYPOS",
                issue_type="misspelling",
            ),
        ),
        used_level=LT_LEVEL_DEFAULT,
        fallback_used=False,
        warning="",
        error="",
    )
    win._apply_languagetool_editor_result(result)
    span = win._find_languagetool_issue_at(1)
    assert span is not None
    calls: list[bool] = []
    monkeypatch.setattr(
        win,
        "_schedule_languagetool_editor_check",
        lambda *, immediate=False: calls.append(bool(immediate)),
    )
    win._apply_languagetool_hint_replacement(span, "the")
    assert win._detail_translation.toPlainText() == "the value"
    assert calls == [True]
