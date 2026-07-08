"""Regression tests for MainWindow TZP write-back helper plumbing."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from translationzed_py.core import parse
from translationzed_py.core.model import Status
from translationzed_py.core.tzp_comment_policy import TZP_COMMENT_PREFIX_DEFAULT
from translationzed_py.gui import main_window_panel_helpers as panel_helpers


class _ChangedRowsModel:
    def changed_rows_with_source(self):
        return [("A", "Source", "Hola", int(Status.TRANSLATED))]


def test_status_comment_writeback_options_use_fixed_string_prefix() -> None:
    """Scenario-injected write-back must pass a real prefix string to core save."""
    win = SimpleNamespace(
        _prefs_extras={"TZP_STATUS_COMMENT_WRITEBACK": "true"},
        _current_model=_ChangedRowsModel(),
    )

    options = panel_helpers._status_comment_writeback_options(
        win,
        include_current_model_overrides=True,
    )

    assert options.enabled is True
    assert options.comment_prefix == TZP_COMMENT_PREFIX_DEFAULT
    assert isinstance(options.comment_prefix, str)
    assert options.status_by_key == {"A": Status.TRANSLATED}


def test_save_parsed_file_with_writeback_accepts_helper_options(tmp_path: Path) -> None:
    """The GUI adapter path should write TZP comments without descriptor errors."""
    path = tmp_path / "ui.txt"
    path.write_text('A = "Hi"\nB = "Bye"\n', encoding="utf-8")
    parsed_file = parse(path)
    win = SimpleNamespace(
        _prefs_extras={"TZP_STATUS_COMMENT_WRITEBACK": "true"},
        _current_model=_ChangedRowsModel(),
    )
    options = panel_helpers._status_comment_writeback_options(
        win,
        include_current_model_overrides=True,
    )

    panel_helpers._save_parsed_file_with_writeback(
        win,
        parsed_file,
        {"A": "Hola"},
        "utf-8",
        options,
    )

    assert path.read_text(encoding="utf-8") == (
        'A = "Hola" -- TZP:TRANSLATED\nB = "Bye"\n'
    )
