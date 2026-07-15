"""Qt adapter for explicit, community-aware locale creation."""

from __future__ import annotations

from collections.abc import Callable, Iterable

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from translationzed_py.core.locale_creation import (
    COMMUNITY_TRANSLATIONS_FORUM_URL,
    OFFICIAL_TRANSLATIONS_README_URL,
    LocaleCreationError,
    apply_creation_plan,
    build_creation_plan,
)
from translationzed_py.core.project_scanner import LocaleMeta

from .dialogs import LocaleChooserDialog


class LocaleCreationWarningDialog(QDialog):
    """Require acknowledgment of official community coordination guidance."""

    def __init__(
        self,
        *,
        readme_url: str,
        forum_url: str,
        parent=None,
        open_url: Callable[[QUrl], bool] | None = None,
    ) -> None:
        """Build the warning and external-link actions."""
        super().__init__(parent)
        self.setWindowTitle("Before creating a localization")
        self.setModal(True)
        self.setMinimumWidth(620)
        self._open_url = open_url or QDesktopServices.openUrl
        self._readme_url = readme_url
        self._forum_url = forum_url

        layout = QVBoxLayout(self)
        guidance = QLabel(
            "Official Project Zomboid translations are coordinated by the community. "
            "Read the official repository instructions, then check whether your language "
            "already has an active forum topic. Join the existing effort when present; "
            "create a topic when none exists."
        )
        guidance.setWordWrap(True)
        layout.addWidget(guidance)

        links = QHBoxLayout()
        readme = QPushButton("Open official README", self)
        readme.setObjectName("openOfficialReadmeButton")
        readme.clicked.connect(lambda: self._open_external(self._readme_url))
        forum = QPushButton("Open translation forum", self)
        forum.setObjectName("openTranslationForumButton")
        forum.clicked.connect(lambda: self._open_external(self._forum_url))
        links.addWidget(readme)
        links.addWidget(forum)
        layout.addLayout(links)

        self._acknowledged = QCheckBox(
            "I have read the README and checked the forum for an existing language topic.",
            self,
        )
        self._acknowledged.setObjectName("localeGuidanceAcknowledged")
        layout.addWidget(self._acknowledged)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            Qt.Orientation.Horizontal,
            self,
        )
        self._continue = buttons.button(QDialogButtonBox.StandardButton.Ok)
        self._continue.setText("Continue")
        self._continue.setEnabled(False)
        self._acknowledged.toggled.connect(self._continue.setEnabled)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _open_external(self, url: str) -> None:
        if self._open_url(QUrl(url)):
            return
        QMessageBox.warning(
            self,
            "Could not open browser",
            f"Open this address manually:\n{url}",
        )


class LocaleCreationDialog(QDialog):
    """Collect the source locale and metadata for a cloned localization."""

    def __init__(self, locales: Iterable[LocaleMeta], parent=None) -> None:
        """Build locale creation fields."""
        super().__init__(parent)
        self.setWindowTitle("Add localization")
        self.setModal(True)
        self.setMinimumWidth(520)
        self._locales = {meta.code: meta for meta in locales}

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Clone existing locale:"))
        self.source_combo = QComboBox(self)
        for meta in sorted(self._locales.values(), key=lambda item: item.code):
            self.source_combo.addItem(f"{meta.code} — {meta.display_name}", meta.code)
        layout.addWidget(self.source_combo)
        layout.addWidget(QLabel("New locale code:"))
        self.code_edit = QLineEdit(self)
        self.code_edit.setObjectName("newLocaleCodeEdit")
        layout.addWidget(self.code_edit)
        layout.addWidget(QLabel("Display name:"))
        self.name_edit = QLineEdit(self)
        self.name_edit.setObjectName("newLocaleNameEdit")
        layout.addWidget(self.name_edit)
        layout.addWidget(QLabel("Charset:"))
        self.charset_edit = QLineEdit("UTF-8", self)
        self.charset_edit.setObjectName("newLocaleCharsetEdit")
        layout.addWidget(self.charset_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            Qt.Orientation.Horizontal,
            self,
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Create")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def values(self) -> tuple[LocaleMeta | None, str, str, str]:
        """Return current creation inputs without validation."""
        source = self._locales.get(str(self.source_combo.currentData() or ""))
        return (
            source,
            self.code_edit.text().strip(),
            self.name_edit.text().strip(),
            self.charset_edit.text().strip(),
        )


def create_locale_from_chooser(win) -> LocaleMeta | None:
    """Run locale creation for a main-window adapter and return the new locale."""
    warning = LocaleCreationWarningDialog(
        readme_url=OFFICIAL_TRANSLATIONS_README_URL,
        forum_url=COMMUNITY_TRANSLATIONS_FORUM_URL,
        parent=win,
    )
    if warning.exec() != warning.DialogCode.Accepted:
        return None
    dialog = LocaleCreationDialog(win._locales.values(), win)
    if dialog.exec() != dialog.DialogCode.Accepted:
        return None
    source, code, display_name, charset = dialog.values()
    if source is None:
        QMessageBox.warning(win, "Add localization", "Choose a locale to clone.")
        return None
    try:
        plan = build_creation_plan(
            project_root=win._root,
            source=source,
            code=code,
            display_name=display_name,
            charset=charset,
        )
        result = apply_creation_plan(plan)
    except LocaleCreationError as exc:
        QMessageBox.warning(win, "Add localization failed", str(exc))
        return None
    created = LocaleMeta(
        code=plan.code,
        path=result.destination,
        display_name=plan.display_name,
        charset=plan.charset,
    )
    win._locales[created.code] = created
    win.statusBar().showMessage(f"Created localization {created.code}.", 6000)
    return created


def build_locale_chooser(
    locales: Iterable[LocaleMeta],
    parent,
    *,
    preselected: Iterable[str] = (),
) -> LocaleChooserDialog:
    """Build the locale chooser with locale creation wired in."""
    return LocaleChooserDialog(
        locales,
        parent,
        preselected=preselected,
        on_add_locale=lambda: create_locale_from_chooser(parent),
    )


__all__ = [
    "LocaleCreationDialog",
    "LocaleCreationWarningDialog",
    "build_locale_chooser",
    "create_locale_from_chooser",
]
