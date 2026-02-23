"""Test module for preferences dialog branch-heavy edge paths."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QListWidgetItem, QTabWidget

from translationzed_py.gui.preferences_dialog import (
    _TM_IS_PENDING_ROLE,
    _TM_PATH_ROLE,
    _TM_SEGMENT_COUNT_ROLE,
    _TM_STATUS_ROLE,
    PreferencesDialog,
)


def _pending_item(dialog: PreferencesDialog, tm_path: str) -> QListWidgetItem:
    """Create a pending TM list item with required metadata."""
    item = QListWidgetItem("pending", dialog._tm_list)
    item.setData(_TM_PATH_ROLE, tm_path)
    item.setData(_TM_IS_PENDING_ROLE, True)
    item.setData(_TM_STATUS_ROLE, "queued")
    item.setData(_TM_SEGMENT_COUNT_ROLE, -1)
    return item


def test_add_tm_file_item_handles_empty_path_invalid_segments_and_raw_locale_pairs(
    qtbot,
) -> None:
    """Verify TM item creation handles empty path and malformed metadata safely."""
    dialog = PreferencesDialog({}, tm_files=[])
    qtbot.addWidget(dialog)

    dialog._add_tm_file_item({"tm_path": ""})
    assert dialog._tm_list.count() == 0

    dialog._add_tm_file_item(
        {
            "tm_path": "/tmp/import/a.tmx",
            "tm_name": "a",
            "segment_count": "not-a-number",
            "status": "ready",
        }
    )
    text = dialog._tm_list.item(0).text()
    assert "[unmapped]" in text
    assert "[WARNING: 0 segments]" in text

    dialog._add_tm_file_item(
        {
            "tm_path": "/tmp/import/b.tmx",
            "tm_name": "b",
            "source_locale": "EN",
            "target_locale": "BE",
            "source_locale_raw": "en-US",
            "target_locale_raw": "be-BY",
            "segment_count": 5,
            "status": "ready",
        }
    )
    text = dialog._tm_list.item(1).text()
    assert "{en-US->be-BY}" in text


def test_queue_tm_imports_deduplicates_and_marks_pending(monkeypatch, qtbot) -> None:
    """Verify queued TM imports deduplicate paths and mark list items as pending."""
    dialog = PreferencesDialog({}, tm_files=[])
    qtbot.addWidget(dialog)
    monkeypatch.setattr(
        "translationzed_py.gui.preferences_dialog.QFileDialog.getOpenFileNames",
        lambda *_args, **_kwargs: (
            ["/tmp/tm/one.tmx", "/tmp/tm/one.tmx", "/tmp/tm/two.xliff"],
            "",
        ),
    )

    dialog._queue_tm_imports()

    assert dialog._tm_import_paths == ["/tmp/tm/one.tmx", "/tmp/tm/two.xliff"]
    assert dialog._tm_list.count() == 2
    assert bool(dialog._tm_list.item(0).data(_TM_IS_PENDING_ROLE)) is True
    assert bool(dialog._tm_list.item(1).data(_TM_IS_PENDING_ROLE)) is True


def test_remove_selected_tm_items_updates_pending_and_persisted_sets(qtbot) -> None:
    """Verify removing selected TM rows updates pending queue and remove list."""
    dialog = PreferencesDialog(
        {},
        tm_files=[
            {
                "tm_path": "/tmp/ready.tmx",
                "tm_name": "ready",
                "source_locale": "EN",
                "target_locale": "BE",
                "segment_count": 2,
                "status": "ready",
                "enabled": True,
            }
        ],
    )
    qtbot.addWidget(dialog)
    dialog._tm_import_paths = ["/tmp/pending.tmx"]
    pending = _pending_item(dialog, "/tmp/pending.tmx")
    ready = dialog._tm_list.item(0)
    assert ready is not None

    ready.setSelected(True)
    pending.setSelected(True)
    dialog._remove_selected_tm_items()

    assert "/tmp/pending.tmx" not in dialog._tm_import_paths
    assert "/tmp/ready.tmx" in dialog._tm_remove_paths
    assert dialog._tm_list.count() == 0


def test_update_tm_action_state_request_flags_and_browse_helpers(
    tmp_path,
    monkeypatch,
    qtbot,
) -> None:
    """Verify TM action-state banner, request flags, browse helpers, and combo fallback."""
    dialog = PreferencesDialog({}, tm_files=[])
    qtbot.addWidget(dialog)

    resolve_btn = dialog._tm_resolve_btn
    dialog._tm_resolve_btn = None
    dialog._update_tm_action_state()
    dialog._tm_resolve_btn = resolve_btn

    _pending_item(dialog, "/tmp/pending-a.tmx")
    for idx in range(3):
        item = QListWidgetItem(f"ready-{idx}", dialog._tm_list)
        item.setData(_TM_PATH_ROLE, f"/tmp/r{idx}.tmx")
        item.setData(_TM_IS_PENDING_ROLE, False)
        item.setData(_TM_STATUS_ROLE, "ready")
        item.setData(_TM_SEGMENT_COUNT_ROLE, "bad")

    dialog._update_tm_action_state()
    assert dialog._tm_resolve_btn is not None
    assert dialog._tm_resolve_btn.isEnabled() is True
    assert dialog._tm_zero_segment_banner is not None
    assert dialog._tm_zero_segment_banner.isHidden() is False
    assert "..." in dialog._tm_zero_segment_banner.text()

    dialog._tm_zero_segment_banner = None
    dialog._update_tm_action_state()

    accepted: list[str] = []
    monkeypatch.setattr(dialog, "accept", lambda: accepted.append("accept"))
    dialog._request_tm_export()
    dialog._request_tm_rebuild()
    assert dialog._tm_export_tmx is True
    assert dialog._tm_rebuild is True
    assert accepted == ["accept", "accept"]

    picked_root = tmp_path / "picked-root"
    picked_tm = tmp_path / "picked-tm"
    monkeypatch.setattr(
        "translationzed_py.gui.preferences_dialog.QFileDialog.getExistingDirectory",
        lambda _self, title, _start: str(
            picked_root if "Project Root" in title else picked_tm
        ),
    )
    dialog._browse_root()
    dialog._browse_tm_import_dir()
    assert dialog._default_root_edit.text() == str(picked_root)
    assert dialog._tm_import_dir_edit.text() == str(picked_tm)

    current_scope = dialog._search_scope_combo.currentData()
    PreferencesDialog._set_combo_value(dialog._search_scope_combo, "MISSING")
    assert dialog._search_scope_combo.currentData() == current_scope


def test_initial_tab_selects_requested_preferences_section(qtbot) -> None:
    """Verify optional initial-tab key opens the matching preferences section."""
    dialog = PreferencesDialog({}, tm_files=[], initial_tab="qa")
    qtbot.addWidget(dialog)
    tabs = dialog.findChild(QTabWidget)
    assert tabs is not None
    assert tabs.tabText(tabs.currentIndex()) == "QA"
