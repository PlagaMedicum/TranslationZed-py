"""Test module for main-window replace, merge, clipboard, and wrap branches."""

from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QItemSelectionModel, Qt
from PySide6.QtGui import QGuiApplication, QStandardItem, QStandardItemModel

from translationzed_py.gui import MainWindow
from translationzed_py.gui import main_window as mw


def _make_project(tmp_path: Path) -> Path:
    """Create a minimal EN/BE project fixture."""
    root = tmp_path / "proj"
    root.mkdir()
    for locale, text in (("EN", "English"), ("BE", "Belarusian")):
        (root / locale).mkdir()
        (root / locale / "language.txt").write_text(
            f"text = {text},\ncharset = UTF-8,\n",
            encoding="utf-8",
        )
    (root / "EN" / "ui.txt").write_text('UI_OK = "OK"\n', encoding="utf-8")
    (root / "BE" / "ui.txt").write_text('UI_OK = "Добра"\n', encoding="utf-8")
    return root


def _build_table_model(parent) -> QStandardItemModel:  # type: ignore[no-untyped-def]
    """Build a two-row model with editable translation column."""
    model = QStandardItemModel(2, 4, parent)
    rows = (
        ("KEY_0", "Source 0", "Value 0", "OK"),
        ("KEY_1", "Source 1", "Value 1", "TODO"),
    )
    for row_idx, values in enumerate(rows):
        for col_idx, value in enumerate(values):
            model.setItem(row_idx, col_idx, QStandardItem(value))
    return model


class _DialogStub:
    """Replace-files dialog stub with configurable confirmation result."""

    _confirm = True
    _instances: list["_DialogStub"] = []

    def __init__(self, counts, scope_label: str, _parent) -> None:  # type: ignore[no-untyped-def]
        self.counts = list(counts)
        self.scope_label = scope_label
        self.exec_calls = 0
        _DialogStub._instances.append(self)

    def exec(self) -> int:
        """Record exec invocation."""
        self.exec_calls += 1
        return 0

    def confirmed(self) -> bool:
        """Return the current configured confirmation result."""
        return bool(self._confirm)


class _WarningSink:
    """QMessageBox stub collecting warning title/text pairs."""

    warnings: list[tuple[str, str]] = []

    @staticmethod
    def warning(_parent, title: str, text: str) -> int:
        """Capture warning messages."""
        _WarningSink.warnings.append((title, text))
        return 0


def test_replace_all_covers_guards_confirmation_and_apply_paths(
    qtbot,
    tmp_path,
    monkeypatch,
) -> None:
    """Verify replace-all flow covers guard, plan, confirm, and apply branches."""
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)

    current_path = root / "BE" / "ui.txt"
    request_box: dict[str, object | None] = {
        "value": SimpleNamespace(
            pattern=re.compile("OK"),
            replacement="GOOD",
            use_regex=False,
            matches_empty=False,
            has_group_ref=False,
        )
    }
    files_box: dict[str, list[Path]] = {"value": [current_path]}
    plan_box: dict[str, object | None] = {"value": None}
    apply_box = {"value": True}
    count_hits: list[str] = []
    apply_hits: list[str] = []
    schedule_hits: list[str] = []

    class _Service:
        """Search/replace service stub for run-plan and apply phases."""

        def __init__(self) -> None:
            self.plan_calls = 0
            self.apply_calls = 0

        def build_replace_all_run_plan(self, **kwargs):  # type: ignore[no-untyped-def]
            self.plan_calls += 1
            _ = kwargs["display_name"](kwargs["files"][0])
            kwargs["count_in_current"]()
            kwargs["count_in_file"](kwargs["files"][0])
            return plan_box["value"]

        def apply_replace_all(self, **kwargs):  # type: ignore[no-untyped-def]
            self.apply_calls += 1
            kwargs["apply_in_current"]()
            kwargs["apply_in_file"](kwargs["files"][0])
            return bool(apply_box["value"])

    service = _Service()
    win._search_replace_service = service  # type: ignore[assignment]
    win._current_pf = SimpleNamespace(path=current_path)
    monkeypatch.setattr(win, "_prepare_replace_request", lambda: request_box["value"])
    monkeypatch.setattr(win, "_files_for_scope", lambda _scope: list(files_box["value"]))
    monkeypatch.setattr(win, "_replace_all_count_in_model", lambda *_args: count_hits.append("model") or 2)
    monkeypatch.setattr(
        win,
        "_replace_all_count_in_file",
        lambda *_args: count_hits.append("file") or 3,
    )
    monkeypatch.setattr(win, "_replace_all_in_model", lambda *_args: apply_hits.append("model") or True)
    monkeypatch.setattr(win, "_replace_all_in_file", lambda *_args: apply_hits.append("file") or True)
    monkeypatch.setattr(win, "_schedule_search", lambda: schedule_hits.append("search"))
    monkeypatch.setattr(mw, "ReplaceFilesDialog", _DialogStub)
    _DialogStub._instances.clear()

    win._current_model = None
    win._replace_all()
    assert service.plan_calls == 0

    win._current_model = object()  # type: ignore[assignment]
    request_box["value"] = None
    win._replace_all()
    assert service.plan_calls == 0

    request_box["value"] = SimpleNamespace(
        pattern=re.compile("OK"),
        replacement="GOOD",
        use_regex=False,
        matches_empty=False,
        has_group_ref=False,
    )
    files_box["value"] = []
    win._replace_all()
    assert service.plan_calls == 0

    files_box["value"] = [current_path]
    plan_box["value"] = None
    win._replace_all()
    assert service.plan_calls == 1
    assert service.apply_calls == 0

    plan_box["value"] = SimpleNamespace(
        run_replace=False,
        show_confirmation=False,
        counts=(),
        scope_label="Selection",
    )
    win._replace_all()
    assert service.plan_calls == 2
    assert service.apply_calls == 0

    plan_box["value"] = SimpleNamespace(
        run_replace=True,
        show_confirmation=True,
        counts=((str(current_path), 1),),
        scope_label="Selection",
    )
    _DialogStub._confirm = False
    win._replace_all()
    assert service.plan_calls == 3
    assert service.apply_calls == 0
    assert _DialogStub._instances[-1].exec_calls == 1

    _DialogStub._confirm = True
    apply_box["value"] = False
    win._replace_all()
    assert service.plan_calls == 4
    assert service.apply_calls == 1
    assert schedule_hits == []

    apply_box["value"] = True
    win._replace_all()
    assert service.plan_calls == 5
    assert service.apply_calls == 2
    assert schedule_hits == ["search"]
    assert count_hits == ["model", "file", "model", "file", "model", "file", "model", "file", "model", "file"]
    assert apply_hits == ["model", "file", "model", "file"]
    win._current_model = None
    win._current_pf = None


def test_replace_helpers_cover_error_and_success_branches(
    qtbot,
    tmp_path,
    monkeypatch,
) -> None:
    """Verify replace helper methods cover parse, regex, dirty, and warning branches."""
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)
    monkeypatch.setattr(mw, "QMessageBox", _WarningSink)
    _WarningSink.warnings.clear()

    model = _build_table_model(win.table)
    win.table.setModel(model)
    win._current_model = model  # type: ignore[assignment]
    win.table.setCurrentIndex(model.index(0, 2))
    current_path = root / "BE" / "ui.txt"
    win._current_pf = SimpleNamespace(path=current_path)

    parse_errors: list[tuple[Path, str]] = []
    dirty_calls: list[tuple[Path, bool]] = []
    monkeypatch.setattr(
        win,
        "_prepare_replace_request",
        lambda: SimpleNamespace(
            pattern=re.compile("Value"),
            replacement="Replaced",
            use_regex=False,
            matches_empty=False,
            has_group_ref=False,
        ),
    )
    monkeypatch.setattr(win, "_report_parse_error", lambda path, exc: parse_errors.append((path, str(exc))))
    monkeypatch.setattr(win.fs_model, "set_dirty", lambda path, value: dirty_calls.append((path, bool(value))))

    mode = {"count_file": "parse", "apply_file": "parse"}

    class _Service:
        """Service stub to drive specific exceptional and success branches."""

        @staticmethod
        def apply_replace_in_row(**_kwargs):  # type: ignore[no-untyped-def]
            raise re.error("replace-row-fail")

        @staticmethod
        def count_replace_all_in_rows(**_kwargs):  # type: ignore[no-untyped-def]
            raise re.error("count-rows-fail")

        @staticmethod
        def count_replace_all_in_file(path, **_kwargs):  # type: ignore[no-untyped-def]
            if mode["count_file"] == "parse":
                raise mw._ReplaceAllFileParseError(path=path, original=ValueError("count-parse-fail"))
            raise re.error("count-file-regex-fail")

        @staticmethod
        def apply_replace_all_in_rows(**_kwargs):  # type: ignore[no-untyped-def]
            raise re.error("apply-rows-fail")

        @staticmethod
        def apply_replace_all_in_file(path, **_kwargs):  # type: ignore[no-untyped-def]
            if mode["apply_file"] == "parse":
                raise mw._ReplaceAllFileParseError(path=path, original=ValueError("apply-parse-fail"))
            if mode["apply_file"] == "regex":
                raise re.error("apply-file-regex-fail")
            return SimpleNamespace(changed_any=mode["apply_file"] == "changed")

    win._search_replace_service = _Service()  # type: ignore[assignment]

    win._replace_current()
    assert ("Replace failed", "replace-row-fail") in _WarningSink.warnings

    assert (
        win._replace_all_count_in_model(
            re.compile("Value"),
            "Replaced",
            False,
            False,
            False,
        )
        is None
    )

    assert (
        win._replace_all_count_in_file(
            current_path,
            re.compile("Value"),
            "Replaced",
            False,
            False,
            False,
        )
        is None
    )
    assert parse_errors[-1] == (current_path, "count-parse-fail")

    mode["count_file"] = "regex"
    assert (
        win._replace_all_count_in_file(
            current_path,
            re.compile("Value"),
            "Replaced",
            False,
            False,
            False,
        )
        is None
    )
    assert ("Replace failed", "count-file-regex-fail") in _WarningSink.warnings

    assert (
        win._replace_all_in_model(
            re.compile("Value"),
            "Replaced",
            False,
            False,
            False,
        )
        is False
    )

    assert (
        win._replace_all_in_file(
            current_path,
            re.compile("Value"),
            "Replaced",
            False,
            False,
            False,
        )
        is False
    )
    assert parse_errors[-1] == (current_path, "apply-parse-fail")

    mode["apply_file"] = "regex"
    assert (
        win._replace_all_in_file(
            current_path,
            re.compile("Value"),
            "Replaced",
            False,
            False,
            False,
        )
        is False
    )
    assert ("Replace failed", "apply-file-regex-fail") in _WarningSink.warnings

    mode["apply_file"] = "changed"
    assert (
        win._replace_all_in_file(
            current_path,
            re.compile("Value"),
            "Replaced",
            False,
            False,
            False,
        )
        is True
    )
    assert dirty_calls[-1] == (current_path, True)

    mode["apply_file"] = "unchanged"
    dirty_count = len(dirty_calls)
    assert (
        win._replace_all_in_file(
            current_path,
            re.compile("Value"),
            "Replaced",
            False,
            False,
            False,
        )
        is True
    )
    assert len(dirty_calls) == dirty_count
    win._current_model = None
    win._current_pf = None


def test_merge_view_apply_and_active_state_cover_selection_paths(
    qtbot,
    tmp_path,
    monkeypatch,
) -> None:
    """Verify merge view build/apply handles incomplete and complete selection states."""
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)
    monkeypatch.setattr(mw, "QMessageBox", _WarningSink)
    _WarningSink.warnings.clear()

    rows = [
        SimpleNamespace(key="A", source_value="S-A", original_value="O-A", cache_value="C-A"),
        SimpleNamespace(key="B", source_value="S-B", original_value="O-B", cache_value="C-B"),
    ]
    path = root / "BE" / "ui.txt"
    win._build_merge_view(path, rows)
    assert win._merge_container is not None
    first_container = win._merge_container

    win._build_merge_view(path, rows)
    assert win._merge_container is not None
    assert win._merge_container is not first_container
    assert len(win._merge_rows) == 2
    assert win._merge_apply_btn is not None
    assert win._merge_apply_btn.isEnabled() is False

    win._apply_merge_resolutions()
    assert _WarningSink.warnings[-1] == (
        "Incomplete selection",
        "Choose Original or Cache for every row.",
    )

    _key_a, orig_a, _cache_a, btn_orig_a, _btn_cache_a = win._merge_rows[0]
    _key_b, _orig_b, cache_b, _btn_orig_b, btn_cache_b = win._merge_rows[1]
    btn_orig_a.setChecked(True)
    btn_cache_b.setChecked(True)
    win._update_merge_apply_enabled()
    assert win._merge_apply_btn.isEnabled() is True

    class _Loop:
        """Event-loop stub used to assert quit behavior."""

        def __init__(self) -> None:
            self.quit_calls = 0

        def isRunning(self) -> bool:
            """Report loop as currently running."""
            return True

        def quit(self) -> None:
            """Count quit calls."""
            self.quit_calls += 1

    loop = _Loop()
    win._merge_loop = loop  # type: ignore[assignment]
    win._apply_merge_resolutions()
    assert loop.quit_calls == 1
    assert win._merge_result == {
        "A": (orig_a.text(), "original"),
        "B": (cache_b.text(), "cache"),
    }

    win._set_merge_active(True)
    assert win.tree.isEnabled() is False
    assert win.table.isEnabled() is False
    assert win._detail_panel.isHidden() is True
    assert win._right_stack.currentWidget() is win._merge_container

    win._set_merge_active(False)
    assert win.tree.isEnabled() is True
    assert win.table.isEnabled() is True
    assert win._detail_panel.isHidden() is False
    assert win._right_stack.currentWidget() is win._table_container


def test_copy_cut_and_paste_cover_row_and_selection_macro_paths(
    qtbot,
    tmp_path,
    monkeypatch,
) -> None:
    """Verify clipboard actions cover full-row copy, single-cell copy, cut, and paste modes."""
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)

    model = _build_table_model(win.table)
    win.table.setModel(model)
    win._current_model = model  # type: ignore[assignment]
    clipboard = QGuiApplication.clipboard()

    sel = win.table.selectionModel()
    assert sel is not None
    sel.clearSelection()
    sel.select(
        model.index(0, 0),
        QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows,
    )
    win._copy_selection()
    assert clipboard.text() == "KEY_0\tSource 0\tValue 0\tOK"

    sel.clearSelection()
    win.table.setCurrentIndex(model.index(1, 2))
    win._copy_selection()
    assert clipboard.text() == "Value 1"

    win.table.setCurrentIndex(model.index(1, 1))
    before_cut = model.index(1, 2).data(Qt.EditRole)
    win._cut_selection()
    assert model.index(1, 2).data(Qt.EditRole) == before_cut

    win.table.setCurrentIndex(model.index(1, 2))
    win._cut_selection()
    assert model.index(1, 2).data(Qt.EditRole) == ""
    assert clipboard.text() == "Value 1"

    clipboard.setText("Paste One")
    win.table.setCurrentIndex(model.index(0, 2))
    monkeypatch.setattr(win, "_selected_rows", lambda: [0])
    win._paste_selection()
    assert model.index(0, 2).data(Qt.EditRole) == "Paste One"

    class _UndoStack:
        """Undo-stack stub for multi-row paste macro assertions."""

        def __init__(self) -> None:
            self.calls: list[str] = []

        def beginMacro(self, _label: str) -> None:
            """Record begin-macro call."""
            self.calls.append("begin")

        def endMacro(self) -> None:
            """Record end-macro call."""
            self.calls.append("end")

    stack = _UndoStack()
    model.undo_stack = stack  # type: ignore[attr-defined]
    clipboard.setText("Paste Many")
    monkeypatch.setattr(win, "_selected_rows", lambda: [0, 1])
    win.table.setCurrentIndex(model.index(0, 2))
    win._paste_selection()
    assert model.index(0, 2).data(Qt.EditRole) == "Paste Many"
    assert model.index(1, 2).data(Qt.EditRole) == "Paste Many"
    assert stack.calls == ["begin", "end"]
    win._current_model = None
    win._current_pf = None


def test_wrap_mode_and_large_file_mode_cover_toggle_and_tooltip_paths(
    qtbot,
    tmp_path,
    monkeypatch,
) -> None:
    """Verify wrap and large-file mode helpers cover preference and tooltip branches."""
    root = _make_project(tmp_path)
    win = MainWindow(str(root), selected_locales=["BE"])
    qtbot.addWidget(win)

    wrap_calls: list[str] = []
    monkeypatch.setattr(win, "_apply_row_height_mode", lambda: wrap_calls.append("row_height"))
    monkeypatch.setattr(win, "_clear_row_height_cache", lambda: wrap_calls.append("clear_cache"))
    monkeypatch.setattr(win, "_schedule_row_resize", lambda: wrap_calls.append("resize"))

    win._wrap_text = False
    win._wrap_text_user = True
    win._large_file_mode = False
    win._apply_wrap_mode()
    assert win._wrap_text is True
    assert wrap_calls == ["row_height", "clear_cache", "resize"]
    assert getattr(win, "act_wrap", None) is not None
    assert win.act_wrap.toolTip() == "Wrap long strings in table"

    win._large_file_mode = True
    win._apply_wrap_mode()
    assert win.act_wrap.toolTip() == "Wrap enabled; large-file mode active"

    toggle_calls: list[str] = []
    monkeypatch.setattr(win, "_apply_wrap_mode", lambda: toggle_calls.append("wrap"))
    monkeypatch.setattr(win, "_persist_preferences", lambda: toggle_calls.append("persist"))
    win._toggle_wrap_text(False)
    assert win._wrap_text_user is False
    assert toggle_calls == ["wrap", "persist"]

    large_calls: list[str] = []
    monkeypatch.setattr(win, "_apply_wrap_mode", lambda: large_calls.append("wrap"))
    monkeypatch.setattr(
        win,
        "_apply_text_visual_options",
        lambda: large_calls.append("visual"),
    )
    win._large_text_optimizations = True
    win._large_file_mode = False
    monkeypatch.setattr(win, "_is_large_file", lambda: True)
    win._update_large_file_mode()
    assert win._large_file_mode is True
    assert large_calls == ["wrap", "visual"]

    large_calls.clear()
    win._update_large_file_mode()
    assert large_calls == []

    win._large_text_optimizations = False
    win._update_large_file_mode()
    assert win._large_file_mode is False
    assert large_calls == ["wrap", "visual"]
