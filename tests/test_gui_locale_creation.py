"""Tests for locale-creation GUI composition."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QCheckBox, QPushButton, QWidget

from translationzed_py.core.project_scanner import LocaleMeta
from translationzed_py.gui import locale_creation as locale_ui


class _AcceptedWarning:
    class DialogCode:
        Accepted = 1

    def __init__(self, *_args, **_kwargs) -> None:
        pass

    def exec(self) -> int:
        return self.DialogCode.Accepted


class _StatusBar:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def showMessage(self, message: str, _timeout: int) -> None:  # noqa: N802
        self.messages.append(message)


class _Window:
    def __init__(self, root: Path, source: LocaleMeta) -> None:
        self._root = root
        self._locales = {source.code: source}
        self._status_bar = _StatusBar()

    def statusBar(self) -> _StatusBar:  # noqa: N802
        return self._status_bar


def _source(root: Path) -> LocaleMeta:
    path = root / "RU"
    path.mkdir()
    (path / "language.txt").write_text(
        'text = "Russian",\ncharset = UTF-8,\n', encoding="utf-8"
    )
    (path / "ui.txt").write_text('A = "text"\n', encoding="utf-8")
    return LocaleMeta("RU", path, "Russian", "utf-8")


def test_warning_requires_acknowledgment_and_opens_both_links(qtbot) -> None:
    """Require community-guidance acknowledgment and expose both links."""
    opened: list[str] = []
    dialog = locale_ui.LocaleCreationWarningDialog(
        readme_url="https://example.test/readme",
        forum_url="https://example.test/forum",
        open_url=lambda url: opened.append(url.toString()) or True,
    )
    qtbot.addWidget(dialog)

    assert dialog._continue.isEnabled() is False
    dialog.findChild(QPushButton, "openOfficialReadmeButton").click()
    dialog.findChild(QPushButton, "openTranslationForumButton").click()
    dialog.findChild(QCheckBox, "localeGuidanceAcknowledged").setChecked(True)

    assert opened == ["https://example.test/readme", "https://example.test/forum"]
    assert dialog._continue.isEnabled() is True


def test_creation_dialog_returns_source_and_metadata(qtbot, tmp_path: Path) -> None:
    """Return the chosen clone source and new locale metadata."""
    source = LocaleMeta("RU", tmp_path / "RU", "Russian", "cp1251")
    dialog = locale_ui.LocaleCreationDialog([source])
    qtbot.addWidget(dialog)
    dialog.code_edit.setText("UA")
    dialog.name_edit.setText("Ukrainian")
    dialog.charset_edit.setText("UTF-8")

    assert dialog.values() == (source, "UA", "Ukrainian", "UTF-8")


def test_create_locale_composes_warning_dialog_and_core_service(
    tmp_path: Path, monkeypatch
) -> None:
    """Create and register a locale only after accepted dialogs."""
    source = _source(tmp_path)
    win = _Window(tmp_path, source)

    class _CreationDialog(_AcceptedWarning):
        def values(self):
            return source, "UA", "Ukrainian", "utf-8"

    monkeypatch.setattr(locale_ui, "LocaleCreationWarningDialog", _AcceptedWarning)
    monkeypatch.setattr(locale_ui, "LocaleCreationDialog", _CreationDialog)

    created = locale_ui.create_locale_from_chooser(win)

    assert created == win._locales["UA"]
    assert created is not None and created.path.is_dir()
    assert win._status_bar.messages == ["Created localization UA."]


def test_create_locale_cancel_and_validation_failures_do_not_write(
    tmp_path: Path, monkeypatch
) -> None:
    """Keep cancellation and invalid input as no-write outcomes."""
    source = _source(tmp_path)
    win = _Window(tmp_path, source)
    warnings: list[str] = []
    monkeypatch.setattr(
        locale_ui.QMessageBox,
        "warning",
        lambda _parent, _title, message: warnings.append(message),
    )

    class _RejectedWarning(_AcceptedWarning):
        def exec(self) -> int:
            return 0

    monkeypatch.setattr(locale_ui, "LocaleCreationWarningDialog", _RejectedWarning)
    assert locale_ui.create_locale_from_chooser(win) is None

    class _MissingSourceDialog(_AcceptedWarning):
        def values(self):
            return None, "UA", "Ukrainian", "utf-8"

    monkeypatch.setattr(locale_ui, "LocaleCreationWarningDialog", _AcceptedWarning)
    monkeypatch.setattr(locale_ui, "LocaleCreationDialog", _MissingSourceDialog)
    assert locale_ui.create_locale_from_chooser(win) is None

    class _InvalidCodeDialog(_AcceptedWarning):
        def values(self):
            return source, "EN", "English", "utf-8"

    monkeypatch.setattr(locale_ui, "LocaleCreationDialog", _InvalidCodeDialog)
    assert locale_ui.create_locale_from_chooser(win) is None
    assert not (tmp_path / "UA").exists()
    assert warnings == ["Choose a locale to clone.", "Reserved locale code: EN"]


def test_warning_reports_browser_failure(qtbot, monkeypatch) -> None:
    """Keep the official URL visible when browser launch fails."""
    warnings: list[str] = []
    monkeypatch.setattr(
        locale_ui.QMessageBox,
        "warning",
        lambda _parent, _title, message: warnings.append(message),
    )
    dialog = locale_ui.LocaleCreationWarningDialog(
        readme_url="https://example.test/readme",
        forum_url="https://example.test/forum",
        open_url=lambda _url: False,
    )
    qtbot.addWidget(dialog)

    dialog.findChild(QPushButton, "openOfficialReadmeButton").click()

    assert warnings == ["Open this address manually:\nhttps://example.test/readme"]


def test_locale_chooser_builder_wires_created_locale(
    qtbot, tmp_path: Path, monkeypatch
) -> None:
    """Compose the chooser with the locale-creation callback."""
    source = LocaleMeta("RU", tmp_path / "RU", "Russian", "utf-8")
    created = LocaleMeta("UA", tmp_path / "UA", "Ukrainian", "utf-8")
    parent = QWidget()
    qtbot.addWidget(parent)
    monkeypatch.setattr(
        locale_ui, "create_locale_from_chooser", lambda _parent: created
    )

    dialog = locale_ui.build_locale_chooser([source], parent, preselected=["RU"])
    qtbot.addWidget(dialog)
    dialog.findChild(QPushButton, "addLocalizationButton").click()

    assert dialog.selected_codes() == ["RU", "UA"]
