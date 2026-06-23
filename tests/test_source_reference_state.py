"""Test module for source reference state."""

from pathlib import Path
from types import SimpleNamespace

from translationzed_py.gui.source_reference_state import (
    apply_source_reference_mode_change,
    apply_source_reference_preferences,
    apply_source_reference_preferences_for_window,
    effective_source_reference_mode_for_window,
    handle_source_reference_changed,
    refresh_source_reference_from_window,
    source_reference_preferences_payload_for_window,
)


def test_apply_source_reference_mode_change_updates_global_mode() -> None:
    """Verify apply source reference mode change updates global mode."""
    extras: dict[str, str] = {}
    overrides: dict[str, str] = {}
    mode, changed = apply_source_reference_mode_change(
        mode="RU",
        root=Path("/tmp/proj"),
        current_path=Path("/tmp/proj/BE/ui.txt"),
        default_mode="EN",
        overrides=overrides,
        extras=extras,
    )
    assert changed is True
    assert mode == "RU"
    assert extras["SOURCE_REFERENCE_MODE"] == "RU"


def test_apply_source_reference_mode_change_updates_file_override() -> None:
    """Verify apply source reference mode change preserves legacy file override map."""
    extras: dict[str, str] = {}
    overrides = {"BE/ui.txt": "EN"}
    mode, changed = apply_source_reference_mode_change(
        mode="RU",
        root=Path("/tmp/proj"),
        current_path=Path("/tmp/proj/BE/ui.txt"),
        default_mode="EN",
        overrides=overrides,
        extras=extras,
    )
    assert changed is True
    assert mode == "RU"
    assert overrides == {"BE/ui.txt": "EN"}
    assert "SOURCE_REFERENCE_FILE_OVERRIDES" not in extras


def test_source_reference_preferences_payload_for_window_omits_removed_controls() -> (
    None
):
    """Visible preferences payload should omit removed source-reference controls."""
    win = SimpleNamespace(
        _prefs_extras={
            "SOURCE_REFERENCE_FALLBACK_CHAIN": "en -> ru",
            "SOURCE_REFERENCE_FALLBACK_PRESETS": '{"be":["ru","en"]}',
        },
    )
    payload = source_reference_preferences_payload_for_window(win)
    assert payload == {}


def test_apply_source_reference_preferences_ignores_removed_legacy_controls() -> None:
    """Legacy source-reference controls should not reappear through the dialog."""
    extras: dict[str, str] = {}
    overrides = {"BE/ui.txt": "RU"}
    changed = apply_source_reference_preferences(
        values={
            "source_reference_fallback_policy": "TARGET_THEN_EN",
            "source_reference_fallback_chain": "RU,KO",
            "source_reference_fallback_presets": '{"BE":["RU","EN"]}',
        },
        overrides=overrides,
        extras=extras,
    )
    assert changed is False
    assert overrides == {"BE/ui.txt": "RU"}
    assert extras == {}


def test_apply_source_reference_preferences_removes_legacy_extras() -> None:
    """Legacy fallback extras should be dropped when preferences are applied."""
    extras = {
        "SOURCE_REFERENCE_FALLBACK_POLICY": "TARGET_THEN_EN",
        "SOURCE_REFERENCE_FALLBACK_CHAIN": "RU,KO",
        "SOURCE_REFERENCE_FALLBACK_PRESETS": '{"BE":["RU","EN"]}',
    }
    changed = apply_source_reference_preferences(
        values={},
        overrides={},
        extras=extras,
    )
    assert changed is True
    assert extras == {}


def test_apply_source_reference_mode_change_returns_unchanged_when_same_mode() -> None:
    """Verify mode change returns unchanged flag for equivalent mode selection."""
    extras: dict[str, str] = {}
    mode, changed = apply_source_reference_mode_change(
        mode="en",
        root=Path("/tmp/proj"),
        current_path=Path("/tmp/proj/BE/ui.txt"),
        default_mode="EN",
        overrides={},
        extras=extras,
    )
    assert mode == "EN"
    assert changed is False
    assert extras == {}


def test_refresh_source_reference_from_window_handles_missing_current_context() -> None:
    """Verify refresh exits cleanly when current file or model is unavailable."""
    win = SimpleNamespace(_current_pf=None, _current_model=None)
    refresh_source_reference_from_window(win)


def test_refresh_source_reference_from_window_applies_lookup_to_current_model() -> None:
    """Verify refresh loads lookup, updates model, and schedules UI sync hooks."""
    calls: list[str] = []
    source_lookup = SimpleNamespace(by_row={1: "src"}, by_hash={})
    model_calls: list[dict[str, object]] = []

    class _Model:
        """Model stub that captures source lookup updates."""

        def set_source_lookup(self, **kwargs):  # type: ignore[no-untyped-def]
            model_calls.append(kwargs)

    path = Path("/tmp/proj/BE/ui.txt")
    win = SimpleNamespace(
        _current_pf=SimpleNamespace(path=path, entries=()),
        _current_model=_Model(),
        _locale_for_path=lambda _path: "BE",
        _load_reference_source=lambda _path, _locale, target_entries: source_lookup,
        _sync_detail_editors=lambda: calls.append("sync"),
        _update_status_bar=lambda: calls.append("status"),
        _schedule_search=lambda: calls.append("search"),
    )

    refresh_source_reference_from_window(win)

    assert model_calls == [
        {"source_values": source_lookup, "source_by_row": source_lookup.by_row}
    ]
    assert calls == ["sync", "status", "search"]


def test_handle_source_reference_changed_returns_when_mode_unchanged(
    monkeypatch,
) -> None:
    """Verify source reference change handler exits when selection does not change mode."""
    win = SimpleNamespace(
        source_ref_combo=object(),
        _root=Path("/tmp/proj"),
        _current_pf=SimpleNamespace(path=Path("/tmp/proj/BE/ui.txt"), entries=()),
        _source_reference_mode="EN",
        _source_reference_file_overrides={},
        _prefs_extras={},
        _search_rows_cache=SimpleNamespace(
            clear=lambda: (_ for _ in ()).throw(RuntimeError("should not clear"))
        ),
        _persist_preferences=lambda: (_ for _ in ()).throw(
            RuntimeError("should not persist")
        ),
    )
    monkeypatch.setattr(
        "translationzed_py.gui.source_reference_ui.source_reference_mode_from_combo",
        lambda _combo, _index: "EN",
    )
    handle_source_reference_changed(win, 0)


def test_effective_source_reference_mode_for_window_keeps_requested_locale(
    monkeypatch,
) -> None:
    """Requested source locale should stay selected; missing files resolve to empty later."""
    monkeypatch.setattr(
        "translationzed_py.gui.source_reference_state.resolve_source_reference_mode_for_path",
        lambda **_kwargs: "KO",
    )
    win = SimpleNamespace(
        _root=Path("/tmp/proj"),
        _source_reference_mode="KO",
        _source_reference_file_overrides={},
        _selected_locales=("RU", "KO"),
    )
    resolved = effective_source_reference_mode_for_window(
        win,
        Path("/tmp/proj/RU/menu.txt"),
        "RU",
    )
    assert resolved == "KO"


def test_apply_source_reference_preferences_for_window_drops_legacy_extras(
    monkeypatch,
) -> None:
    """Removing old source-reference extras should refresh the window once."""
    calls: list[str] = []
    win = SimpleNamespace(
        _source_reference_file_overrides={},
        _prefs_extras={
            "SOURCE_REFERENCE_FALLBACK_POLICY": "TARGET_THEN_EN",
            "SOURCE_REFERENCE_FALLBACK_CHAIN": "RU,KO",
            "SOURCE_REFERENCE_FALLBACK_PRESETS": '{"BE":["RU","EN"]}',
        },
        _search_rows_cache=SimpleNamespace(clear=lambda: calls.append("clear")),
    )

    monkeypatch.setattr(
        "translationzed_py.gui.source_reference_state.sync_source_reference_override_ui_for_window",
        lambda _win: calls.append("sync"),
    )
    monkeypatch.setattr(
        "translationzed_py.gui.source_reference_state.refresh_source_reference_from_window",
        lambda _win: calls.append("refresh"),
    )

    changed = apply_source_reference_preferences_for_window(
        win,
        {
            "source_reference_fallback_policy": "TARGET_THEN_EN",
        },
    )
    assert changed is True
    assert win._prefs_extras == {}
    assert calls == ["clear", "sync", "refresh"]
