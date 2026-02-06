from __future__ import annotations

import contextlib
import html
import os
import re
import sys
import time
import traceback
from collections import OrderedDict
from collections.abc import Iterable, Mapping, Sequence
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path

import xxhash
from PySide6.QtCore import (
    QByteArray,
    QEvent,
    QEventLoop,
    QItemSelectionModel,
    QModelIndex,
    QPoint,
    Qt,
    QTimer,
    QUrl,
)
from PySide6.QtGui import (
    QAction,
    QCursor,
    QDesktopServices,
    QGuiApplication,
    QIcon,
    QKeySequence,
    QTextOption,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QStackedWidget,
    QStyle,
    QTableView,
    QTableWidget,
    QTableWidgetItem,
    QToolBar,
    QToolButton,
    QToolTip,
    QTreeView,
    QVBoxLayout,
    QWidget,
)
from shiboken6 import isValid

from translationzed_py.core import (
    Entry,
    LocaleMeta,
    ParsedFile,
    list_translatable_files,
    parse,
    parse_lazy,
    scan_root_with_errors,
)
from translationzed_py.core.app_config import load as _load_app_config
from translationzed_py.core.en_hash_cache import compute as _compute_en_hashes
from translationzed_py.core.en_hash_cache import read as _read_en_hash_cache
from translationzed_py.core.en_hash_cache import write as _write_en_hash_cache
from translationzed_py.core.model import STATUS_ORDER, Status
from translationzed_py.core.preferences import load as _load_preferences
from translationzed_py.core.preferences import save as _save_preferences
from translationzed_py.core.saver import save
from translationzed_py.core.search import Match as _SearchMatch
from translationzed_py.core.search import SearchField as _SearchField
from translationzed_py.core.search import SearchRow as _SearchRow
from translationzed_py.core.search import iter_matches as _iter_search_matches
from translationzed_py.core.status_cache import (
    CacheEntry,
)
from translationzed_py.core.status_cache import (
    legacy_cache_paths as _legacy_cache_paths,
)
from translationzed_py.core.status_cache import (
    migrate_all as _migrate_status_caches,
)
from translationzed_py.core.status_cache import (
    migrate_paths as _migrate_status_cache_paths,
)
from translationzed_py.core.status_cache import (
    read as _read_status_cache,
)
from translationzed_py.core.status_cache import (
    read_has_drafts_from_path as _read_has_drafts_from_path,
)
from translationzed_py.core.status_cache import (
    read_last_opened_from_path as _read_last_opened_from_path,
)
from translationzed_py.core.status_cache import (
    touch_last_opened as _touch_last_opened,
)
from translationzed_py.core.status_cache import write as _write_status_cache
from translationzed_py.core.tm_store import TMMatch, TMStore

from .delegates import (
    MAX_VISUAL_CHARS,
    KeyDelegate,
    StatusDelegate,
    TextVisualHighlighter,
    VisualTextDelegate,
)
from .dialogs import (
    AboutDialog,
    ConflictChoiceDialog,
    LocaleChooserDialog,
    ReplaceFilesDialog,
    SaveFilesDialog,
    TmLanguageDialog,
)
from .entry_model import TranslationModel
from .fs_model import FsModel
from .perf_trace import PERF_TRACE
from .preferences_dialog import PreferencesDialog

_TEST_DIALOGS_PATCHED = False
_ORIG_QMESSAGEBOX_EXEC = None
_ORIG_QMESSAGEBOX_WARNING = None
_ORIG_QMESSAGEBOX_CRITICAL = None
_ORIG_QMESSAGEBOX_INFORMATION = None


def _in_test_mode() -> bool:
    return bool(os.environ.get("PYTEST_CURRENT_TEST") or os.environ.get("TZP_TESTING"))


def _bool_from_pref(value: object, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    raw = str(value).strip().lower()
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
    return default


def _int_from_pref(value: object, default: int, *, min_value: int, max_value: int) -> int:
    try:
        parsed = int(str(value).strip())
    except (TypeError, ValueError):
        return default
    return max(min_value, min(max_value, parsed))


def _patch_message_boxes_for_tests() -> None:
    global _TEST_DIALOGS_PATCHED
    global _ORIG_QMESSAGEBOX_EXEC
    global _ORIG_QMESSAGEBOX_WARNING
    global _ORIG_QMESSAGEBOX_CRITICAL
    global _ORIG_QMESSAGEBOX_INFORMATION
    if _TEST_DIALOGS_PATCHED or not _in_test_mode():
        return

    _ORIG_QMESSAGEBOX_EXEC = QMessageBox.exec
    _ORIG_QMESSAGEBOX_WARNING = QMessageBox.warning
    _ORIG_QMESSAGEBOX_CRITICAL = QMessageBox.critical
    _ORIG_QMESSAGEBOX_INFORMATION = QMessageBox.information

    def _exec_noop(self) -> int:
        if _in_test_mode():
            return int(QMessageBox.StandardButton.Ok)
        return _ORIG_QMESSAGEBOX_EXEC(self)

    def _warn(*args, **kwargs) -> int:
        if _in_test_mode():
            return int(QMessageBox.StandardButton.Ok)
        return _ORIG_QMESSAGEBOX_WARNING(*args, **kwargs)

    def _critical(*args, **kwargs) -> int:
        if _in_test_mode():
            return int(QMessageBox.StandardButton.Ok)
        return _ORIG_QMESSAGEBOX_CRITICAL(*args, **kwargs)

    def _info(*args, **kwargs) -> int:
        if _in_test_mode():
            return int(QMessageBox.StandardButton.Ok)
        return _ORIG_QMESSAGEBOX_INFORMATION(*args, **kwargs)

    QMessageBox.exec = _exec_noop  # type: ignore[assignment]
    QMessageBox.warning = staticmethod(_warn)
    QMessageBox.critical = staticmethod(_critical)
    QMessageBox.information = staticmethod(_info)
    _TEST_DIALOGS_PATCHED = True


_TM_REBUILD_BATCH = 1000
_TMRebuildLocale = tuple[str, Path, str]
# Avoid blocking UI by deferring detail-panel loads for huge strings.
_DETAIL_LAZY_THRESHOLD = 100_000


def _tm_en_path_for(root: Path, locale: str, path: Path) -> Path | None:
    locale_root = root / locale
    try:
        rel = path.relative_to(locale_root)
    except ValueError:
        try:
            rel_full = path.relative_to(root)
            if rel_full.parts and rel_full.parts[0] == locale:
                rel = Path(*rel_full.parts[1:])
            else:
                return None
        except ValueError:
            return None
    candidate = root / "EN" / rel
    if candidate.exists():
        return candidate
    stem = rel.stem
    for token in (locale, locale.replace(" ", "_")):
        suffix = f"_{token}"
        if stem.endswith(suffix):
            new_stem = stem[: -len(suffix)] + "_EN"
            alt = rel.with_name(new_stem + rel.suffix)
            alt_path = root / "EN" / alt
            if alt_path.exists():
                return alt_path
    return None


def _tm_rebuild_worker(
    root: Path,
    locales: list[_TMRebuildLocale],
    source_locale: str,
    en_encoding: str,
) -> dict[str, int]:
    store = TMStore(root)
    totals = {
        "files": 0,
        "entries": 0,
        "skipped_missing_source": 0,
        "skipped_parse": 0,
        "skipped_empty": 0,
    }
    try:
        for locale, locale_path, target_encoding in locales:
            for target_path in list_translatable_files(locale_path):
                en_path = _tm_en_path_for(root, locale, target_path)
                if en_path is None:
                    totals["skipped_missing_source"] += 1
                    continue
                try:
                    target_pf = parse(target_path, encoding=target_encoding)
                    en_pf = parse(en_path, encoding=en_encoding)
                except Exception:
                    totals["skipped_parse"] += 1
                    continue
                source_by_key = {entry.key: entry.value for entry in en_pf.entries}
                batch: list[tuple[str, str, str]] = []
                for entry in target_pf.entries:
                    value = entry.value
                    if value is None:
                        totals["skipped_empty"] += 1
                        continue
                    value_text = str(value)
                    if not value_text:
                        totals["skipped_empty"] += 1
                        continue
                    source_text = source_by_key.get(entry.key)
                    if not source_text:
                        totals["skipped_missing_source"] += 1
                        continue
                    batch.append((entry.key, str(source_text), value_text))
                    if len(batch) >= _TM_REBUILD_BATCH:
                        totals["entries"] += store.upsert_project_entries(
                            batch,
                            source_locale=source_locale,
                            target_locale=locale,
                            file_path=str(target_path),
                        )
                        batch.clear()
                if batch:
                    totals["entries"] += store.upsert_project_entries(
                        batch,
                        source_locale=source_locale,
                        target_locale=locale,
                        file_path=str(target_path),
                    )
                totals["files"] += 1
    finally:
        store.close()
    return totals


class _CommitPlainTextEdit(QPlainTextEdit):
    def __init__(self, commit_cb, parent=None, *, focus_cb=None) -> None:
        super().__init__(parent)
        self._commit_cb = commit_cb
        self._focus_cb = focus_cb

    def focusOutEvent(self, event) -> None:  # noqa: N802
        super().focusOutEvent(event)
        if self._commit_cb:
            self._commit_cb()

    def focusInEvent(self, event) -> None:  # noqa: N802
        super().focusInEvent(event)
        if self._focus_cb:
            self._focus_cb()


class _SourceLookup(Mapping[str, str]):
    __slots__ = ("_by_row", "_keys", "_by_key")

    def __init__(
        self,
        *,
        by_row: Sequence[str] | None = None,
        keys: list[str] | None = None,
        by_key: dict[str, str] | None = None,
    ) -> None:
        self._by_row = by_row
        self._keys = keys
        self._by_key = by_key

    @property
    def by_row(self) -> Sequence[str] | None:
        return self._by_row

    def _ensure_by_key(self) -> dict[str, str]:
        if self._by_key is None:
            if self._by_row is None or self._keys is None:
                self._by_key = {}
            else:
                by_key: dict[str, str] = {}
                limit = min(len(self._keys), len(self._by_row))
                for idx in range(limit):
                    by_key[self._keys[idx]] = self._by_row[idx]
                self._by_key = by_key
        return self._by_key

    def get(self, key: str, default: str = "") -> str:
        return self._ensure_by_key().get(key, default)

    def __getitem__(self, key: str) -> str:
        return self.get(key, "")

    def __iter__(self):
        return iter(self._ensure_by_key())

    def __len__(self) -> int:
        return len(self._ensure_by_key())


class _LazySourceRows:
    __slots__ = ("_entries",)

    def __init__(self, entries: Sequence[Entry]) -> None:
        self._entries = entries

    def __len__(self) -> int:
        return len(self._entries)

    def __getitem__(self, idx):
        if isinstance(idx, slice):
            start, stop, step = idx.indices(len(self._entries))
            return [self._entries[i].value for i in range(start, stop, step)]
        return self._entries[idx].value

    def length_at(self, idx: int) -> int:
        entries = self._entries
        if hasattr(entries, "meta_at"):
            try:
                meta = entries.meta_at(idx)
                if meta.segments:
                    return sum(meta.segments)
            except Exception:
                return 0
            return 0
        value = entries[idx].value
        return len(value) if value else 0


class MainWindow(QMainWindow):
    """Main window: left file-tree, right translation table."""

    def __init__(
        self,
        project_root: str | None = None,
        *,
        selected_locales: list[str] | None = None,
    ) -> None:
        super().__init__()
        self._startup_aborted = False
        self._root = Path(".").resolve()
        self._default_root = ""
        self._smoke = os.environ.get("TZP_SMOKE", "") == "1"
        self._test_mode = _in_test_mode()
        _patch_message_boxes_for_tests()
        if project_root is None:
            prefs_global = _load_preferences(None)
            default_root = str(prefs_global.get("default_root", "")).strip()
            if default_root and Path(default_root).exists():
                self._root = Path(default_root).resolve()
                self._default_root = default_root
            else:
                picked = QFileDialog.getExistingDirectory(
                    self, "Select Project Root", str(Path.cwd())
                )
                if not picked:
                    self._startup_aborted = True
                    return
                self._root = Path(picked).resolve()
                self._default_root = str(self._root)
                prefs_global["default_root"] = self._default_root
                with contextlib.suppress(Exception):
                    _save_preferences(prefs_global, None)
        else:
            self._root = Path(project_root).resolve()
        if not self._root.exists():
            QMessageBox.warning(self, "Invalid project root", str(self._root))
            self._startup_aborted = True
            return
        self.setWindowTitle(f"TranslationZed-Py – {self._root}")
        self._locales: dict[str, LocaleMeta] = {}
        self._selected_locales: list[str] = []
        self._current_encoding = "utf-8"
        self._app_config = _load_app_config(self._root)
        self._current_pf = None  # type: translationzed_py.core.model.ParsedFile | None
        self._current_model: TranslationModel | None = None
        self._opened_files: set[Path] = set()
        self._cache_map: dict[int, CacheEntry] = {}
        self._conflict_files: dict[Path, dict[str, str]] = {}
        self._conflict_sources: dict[Path, dict[str, str]] = {}
        self._conflict_notified: set[Path] = set()
        self._skip_conflict_check = False
        self._skip_cache_write = False
        self._files_by_locale: dict[str, list[Path]] = {}
        self._en_cache: dict[Path, ParsedFile] = {}
        self._child_windows: list[MainWindow] = []
        self._tm_store: TMStore | None = None
        self._tm_cache: OrderedDict[
            tuple[str, str, str, int, bool, bool], list[TMMatch]
        ] = OrderedDict()
        self._tm_cache_limit = 128
        self._tm_pending: dict[str, dict[str, tuple[str, str, str]]] = {}
        self._tm_source_locale = "EN"
        self._tm_query_pool: ThreadPoolExecutor | None = None
        self._tm_query_future: Future[list[TMMatch]] | None = None
        self._tm_query_key: tuple[str, str, str, int, bool, bool] | None = None
        self._tm_rebuild_pool: ThreadPoolExecutor | None = None
        self._tm_rebuild_future: Future[dict[str, int]] | None = None
        self._tm_rebuild_locales: list[str] = []
        self._tm_rebuild_interactive = False
        self._tm_bootstrap_pending = False

        if not self._smoke and not self._check_en_hash_cache():
            self._startup_aborted = True
            return
        prefs = _load_preferences(self._root)
        self._prompt_write_on_exit = bool(prefs.get("prompt_write_on_exit", True))
        self._wrap_text_user = bool(prefs.get("wrap_text", False))
        self._wrap_text = self._wrap_text_user
        self._large_text_optimizations = bool(
            prefs.get("large_text_optimizations", True)
        )
        if self._test_mode:
            self._prompt_write_on_exit = False
        self._default_root = str(prefs.get("default_root", "") or self._default_root)
        self._search_scope = str(prefs.get("search_scope", "FILE")).upper()
        if self._search_scope not in {"FILE", "LOCALE", "POOL"}:
            self._search_scope = "FILE"
        self._replace_scope = str(prefs.get("replace_scope", "FILE")).upper()
        if self._replace_scope not in {"FILE", "LOCALE", "POOL"}:
            self._replace_scope = "FILE"
        self._search_scope_widget = None
        self._search_scope_action = None
        self._search_scope_icon = None
        self._replace_scope_widget = None
        self._replace_scope_action = None
        self._replace_scope_icon = None
        self._last_locales = list(prefs.get("last_locales", []) or [])
        self._last_root = str(prefs.get("last_root", "") or self._root)
        self._prefs_extras = dict(prefs.get("__extras__", {}))
        layout_reset_rev = str(self._prefs_extras.get("LAYOUT_RESET_REV", "")).strip()
        if layout_reset_rev != "3":
            prefs["window_geometry"] = ""
            for key in (
                "TABLE_KEY_WIDTH",
                "TABLE_STATUS_WIDTH",
                "TABLE_SRC_RATIO",
                "TREE_PANEL_WIDTH",
            ):
                self._prefs_extras.pop(key, None)
            self._prefs_extras["LAYOUT_RESET_REV"] = "3"
            prefs["__extras__"] = dict(self._prefs_extras)
            with contextlib.suppress(Exception):
                _save_preferences(prefs, self._root)
        self._tm_min_score = _int_from_pref(
            self._prefs_extras.get("TM_MIN_SCORE"), 30, min_value=30, max_value=100
        )
        self._tm_origin_project = _bool_from_pref(
            self._prefs_extras.get("TM_ORIGIN_PROJECT"), True
        )
        self._tm_origin_import = _bool_from_pref(
            self._prefs_extras.get("TM_ORIGIN_IMPORT"), True
        )
        geom = str(prefs.get("window_geometry", "")).strip()
        if geom:
            with contextlib.suppress(Exception):
                self.restoreGeometry(QByteArray.fromBase64(geom.encode("ascii")))

        self._tree_last_width = 220
        self._detail_last_height: int | None = None
        self._detail_min_height = 0
        self._detail_syncing = False
        self._detail_dirty = False
        self._detail_pending_row: int | None = None
        self._detail_pending_active = False
        self._large_file_mode = False
        self._current_file_size = 0
        self._merge_active = False
        self._merge_rows: list[
            tuple[str, QTableWidgetItem, QTableWidgetItem, QRadioButton, QRadioButton]
        ] = []
        self._merge_result: dict[str, tuple[str, str]] | None = None
        self._merge_loop: QEventLoop | None = None
        self._merge_apply_btn: QPushButton | None = None
        self._orphan_cache_warned_locales: set[str] = set()
        self._pending_cache_migrations: list[Path] = []
        self._migration_timer: QTimer | None = None
        self._migration_batch_size = 25
        self._migration_count = 0
        self._post_locale_timer = QTimer(self)
        self._post_locale_timer.setSingleShot(True)
        self._post_locale_timer.setInterval(0)
        self._post_locale_timer.timeout.connect(self._run_post_locale_tasks)
        self._tm_update_timer = QTimer(self)
        self._tm_update_timer.setSingleShot(True)
        self._tm_update_timer.setInterval(120)
        self._tm_update_timer.timeout.connect(self._update_tm_suggestions)
        self._tm_flush_timer = QTimer(self)
        self._tm_flush_timer.setSingleShot(True)
        self._tm_flush_timer.setInterval(750)
        self._tm_flush_timer.timeout.connect(self._flush_tm_updates)
        self._tm_query_timer = QTimer(self)
        self._tm_query_timer.setSingleShot(False)
        self._tm_query_timer.setInterval(50)
        self._tm_query_timer.timeout.connect(self._poll_tm_query)
        self._tm_rebuild_timer = QTimer(self)
        self._tm_rebuild_timer.setSingleShot(False)
        self._tm_rebuild_timer.setInterval(100)
        self._tm_rebuild_timer.timeout.connect(self._poll_tm_rebuild)

        self._main_splitter = QSplitter(Qt.Vertical, self)
        self._content_splitter = QSplitter(Qt.Horizontal, self)
        self._main_splitter.addWidget(self._content_splitter)
        self.setCentralWidget(self._main_splitter)
        self._main_splitter.splitterMoved.connect(self._on_main_splitter_moved)
        self._content_splitter.splitterMoved.connect(self._on_content_splitter_moved)

        # ── toolbar ────────────────────────────────────────────────────────
        self.toolbar = QToolBar("Toolbar", self)
        self.toolbar.setMovable(False)
        self.addToolBar(self.toolbar)
        self._updating_status_combo = False
        self.tree_toggle = QToolButton(self)
        self.tree_toggle.setCheckable(True)
        self.tree_toggle.setAutoRaise(True)
        self.tree_toggle.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowLeft)
        )
        self.tree_toggle.setToolTip("Hide side panel")
        self.tree_toggle.toggled.connect(self._toggle_tree_panel)
        self.toolbar.addWidget(self.tree_toggle)
        self.toolbar.addSeparator()
        status_label = QLabel("Status:", self)
        status_label.setContentsMargins(0, 0, 4, 0)
        self.toolbar.addWidget(status_label)
        self.status_combo = QComboBox(self)
        self.status_combo.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        for st in STATUS_ORDER:
            self.status_combo.addItem(st.label(), st)
        self.status_combo.setCurrentIndex(-1)
        self.status_combo.setEnabled(False)
        self.status_combo.currentIndexChanged.connect(self._status_combo_changed)
        self.toolbar.addWidget(self.status_combo)
        self.toolbar.addSeparator()
        self.regex_check = QCheckBox("Regex", self)
        self.regex_check.stateChanged.connect(self._on_search_controls_changed)
        self.regex_help = QLabel(
            '<a href="https://docs.python.org/3/library/re.html">'
            '<span style="vertical-align:super; font-size:smaller;">?</span>'
            "</a>",
            self,
        )
        self.regex_help.setToolTip("Regex help (Python re)")
        self.regex_help.setTextFormat(Qt.RichText)
        self.regex_help.setTextInteractionFlags(Qt.TextBrowserInteraction)
        self.regex_help.setOpenExternalLinks(True)
        self.regex_help.setContentsMargins(0, 0, 4, 0)
        regex_wrap = QWidget(self)
        regex_layout = QHBoxLayout(regex_wrap)
        regex_layout.setContentsMargins(0, 0, 0, 0)
        regex_layout.setSpacing(0)
        regex_layout.addWidget(self.regex_check)
        regex_layout.addWidget(self.regex_help)
        self.toolbar.addWidget(regex_wrap)
        self.search_edit = QLineEdit(self)
        self.search_edit.setPlaceholderText("Search")
        self.search_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.search_edit.setMinimumWidth(320)
        self.search_edit.textChanged.connect(self._on_search_controls_changed)
        self.search_edit.returnPressed.connect(self._trigger_search)
        self.toolbar.addWidget(self.search_edit)
        self.search_prev_btn = QToolButton(self)
        self.search_prev_btn.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowUp)
        )
        self.search_prev_btn.setToolTip("Find previous match")
        self.search_prev_btn.setAutoRaise(True)
        self.search_prev_btn.clicked.connect(self._search_prev)
        self.toolbar.addWidget(self.search_prev_btn)
        self.search_next_btn = QToolButton(self)
        self.search_next_btn.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowDown)
        )
        self.search_next_btn.setToolTip("Find next match")
        self.search_next_btn.setAutoRaise(True)
        self.search_next_btn.clicked.connect(self._search_next)
        self.toolbar.addWidget(self.search_next_btn)
        self.replace_toggle = QToolButton(self)
        self.replace_toggle.setToolButtonStyle(Qt.ToolButtonIconOnly)
        self.replace_toggle.setCheckable(True)
        self.replace_toggle.toggled.connect(self._toggle_replace)
        self._replace_icon = QIcon.fromTheme(
            "edit-find-replace",
            self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload),
        )
        self._replace_icon_active = self._replace_icon
        self._update_replace_toggle_icon(False)
        self.toolbar.addWidget(self.replace_toggle)
        self.search_column_label = QLabel("Search in:", self)
        self.search_column_label.setContentsMargins(8, 0, 4, 0)
        self.toolbar.addWidget(self.search_column_label)
        self.search_mode = QComboBox(self)
        self.search_mode.addItem("Key", 0)
        self.search_mode.addItem("Source", 1)
        self.search_mode.addItem("Trans", 2)
        self.search_mode.setCurrentIndex(2)
        self.search_mode.currentIndexChanged.connect(self._on_search_controls_changed)
        self.toolbar.addWidget(self.search_mode)

        self.addToolBarBreak()
        self.replace_toolbar = QToolBar("Replace", self)
        self.replace_toolbar.setMovable(False)
        self.replace_toolbar.setContentsMargins(0, 0, 0, 0)
        self.addToolBar(self.replace_toolbar)
        self.replace_spacer = QLabel(self)
        self.replace_spacer.setFixedWidth(0)
        self.replace_toolbar.addWidget(self.replace_spacer)
        self.replace_edit = QLineEdit(self)
        self.replace_edit.setPlaceholderText("Replace")
        self.replace_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.replace_edit.setMinimumWidth(self.search_edit.minimumWidth())
        self.replace_edit.textChanged.connect(self._update_replace_enabled)
        self.replace_toolbar.addWidget(self.replace_edit)
        self.replace_btn = QToolButton(self)
        self.replace_btn.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_DialogApplyButton)
        )
        self.replace_btn.setToolTip("Replace current match in Trans")
        self.replace_btn.setAutoRaise(True)
        self.replace_btn.clicked.connect(self._replace_current)
        self.replace_toolbar.addWidget(self.replace_btn)
        self.replace_all_btn = QToolButton(self)
        self.replace_all_btn.setText("All")
        self.replace_all_btn.setToolTip("Replace all matches in this file (Trans)")
        self.replace_all_btn.setAutoRaise(True)
        self.replace_all_btn.clicked.connect(self._replace_all)
        self.replace_toolbar.addWidget(self.replace_all_btn)
        self.replace_toolbar.setVisible(False)
        self._update_replace_enabled()
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(300)
        self._search_timer.timeout.connect(self._run_search)
        self._search_column = 0
        self._last_saved_text = ""
        self._search_rows_cache: OrderedDict[
            tuple[Path, bool, bool], tuple[tuple[int, int, int], list[_SearchRow]]
        ] = OrderedDict()
        self._search_cache_max = 64
        self._search_cache_row_limit = 5000
        self._replace_visible = False
        self._search_progress_text = ""
        self._row_resize_timer = QTimer(self)
        self._row_resize_timer.setSingleShot(True)
        self._row_resize_timer.setInterval(80)
        self._row_resize_timer.timeout.connect(self._resize_visible_rows)
        self._scroll_idle_timer = QTimer(self)
        self._scroll_idle_timer.setSingleShot(True)
        self._scroll_idle_timer.setInterval(200)
        self._scroll_idle_timer.timeout.connect(self._on_scroll_idle)
        self._scrolling = False
        self._row_height_cache: dict[int, int] = {}
        self._row_height_cache_key: tuple[int, ...] | None = None
        self._tooltip_timer = QTimer(self)
        self._tooltip_timer.setSingleShot(True)
        self._tooltip_timer.setInterval(900)
        self._tooltip_timer.timeout.connect(self._show_delayed_tooltip)
        self._tooltip_index = QModelIndex()
        self._tooltip_pos = QPoint()
        self._tree_width_timer = QTimer(self)
        self._tree_width_timer.setSingleShot(True)
        self._tree_width_timer.setInterval(250)
        self._tree_width_timer.timeout.connect(self._persist_tree_width)
        self._row_cache_margin_pct = 0.5
        self._large_file_row_threshold = 5000
        self._large_file_bytes_threshold = 1_000_000
        self._prefetch_pending = False
        self._pending_row_span: tuple[int, int] | None = None
        self._lazy_parse_min_bytes = 1_000_000
        self._lazy_row_prefetch_margin = 200

        def _pref_bool(name: str, default: bool) -> bool:
            raw = str(self._prefs_extras.get(name, "")).strip().lower()
            if raw in {"1", "true", "yes", "on"}:
                return True
            if raw in {"0", "false", "no", "off"}:
                return False
            return default

        def _pref_int(name: str) -> int | None:
            raw = str(self._prefs_extras.get(name, "")).strip()
            if not raw:
                return None
            try:
                val = int(raw)
            except ValueError:
                return None
            return val if val > 0 else None

        def _pref_float(name: str) -> float | None:
            raw = str(self._prefs_extras.get(name, "")).strip()
            if not raw:
                return None
            try:
                val = float(raw)
            except ValueError:
                return None
            return val if 0.05 <= val <= 0.95 else None

        self._key_column_width: int | None = _pref_int("TABLE_KEY_WIDTH")
        self._status_column_width: int | None = _pref_int("TABLE_STATUS_WIDTH")
        self._source_translation_ratio = _pref_float("TABLE_SRC_RATIO") or 0.5
        self._table_layout_guard = False
        self._user_resized_columns = bool(_pref_float("TABLE_SRC_RATIO"))
        self._tree_last_width = _pref_int("TREE_PANEL_WIDTH") or self._tree_last_width
        self._visual_whitespace = _pref_bool("TEXT_SHOW_WHITESPACE", False)
        self._visual_highlight = _pref_bool("TEXT_HIGHLIGHT", False)

        # ── menu bar ───────────────────────────────────────────────────────
        menubar = self.menuBar()
        self.menu_general = menubar.addMenu("General")
        self.menu_edit = menubar.addMenu("Edit")
        self.menu_view = menubar.addMenu("View")
        self.menu_tm = menubar.addMenu("TM")
        self.menu_help = menubar.addMenu("Help")

        # ── left pane: side panel (Files / TM / Search) ─────────────────────
        self._left_panel = QWidget()
        left_layout = QVBoxLayout(self._left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(4)

        toggle_bar = QWidget(self._left_panel)
        toggle_layout = QHBoxLayout(toggle_bar)
        toggle_layout.setContentsMargins(6, 4, 6, 4)
        toggle_layout.setSpacing(6)
        self._left_group = QButtonGroup(self)
        self._left_group.setExclusive(True)
        self._left_files_btn = QToolButton(self)
        self._left_files_btn.setText("Files")
        self._left_files_btn.setCheckable(True)
        self._left_tm_btn = QToolButton(self)
        self._left_tm_btn.setText("TM")
        self._left_tm_btn.setCheckable(True)
        self._left_search_btn = QToolButton(self)
        self._left_search_btn.setText("Search")
        self._left_search_btn.setCheckable(True)
        for btn, idx in (
            (self._left_files_btn, 0),
            (self._left_tm_btn, 1),
            (self._left_search_btn, 2),
        ):
            btn.setAutoRaise(True)
            self._left_group.addButton(btn, idx)
            toggle_layout.addWidget(btn)
        toggle_layout.addStretch(1)
        self._left_group.buttonClicked.connect(self._on_left_panel_changed)

        self._left_stack = QStackedWidget(self._left_panel)

        self.tree = QTreeView()
        self._init_locales(selected_locales)
        if not self._selected_locales:
            self._startup_aborted = True
            return
        lazy_tree = len(self._selected_locales) > 1
        self.fs_model = FsModel(
            self._root,
            [self._locales[c] for c in self._selected_locales],
            lazy=lazy_tree,
        )
        self.tree.setModel(self.fs_model)
        self.tree.expanded.connect(self._on_tree_expanded)
        # prevent in-place renaming on double-click; we use double-click to open
        self.tree.setEditTriggers(QAbstractItemView.NoEditTriggers)
        if self.fs_model.is_lazy():
            if len(self._selected_locales) == 1:
                idx = self.fs_model.index(0, 0)
                if idx.isValid():
                    self.fs_model.ensure_loaded_for_index(idx)
                    self.tree.expand(idx)
        else:
            self.tree.expandAll()
        self._schedule_post_locale_tasks()
        self.tree.activated.connect(self._file_chosen)  # Enter / platform activation
        self.tree.doubleClicked.connect(self._file_chosen)
        self._left_stack.addWidget(self.tree)

        self._tm_panel = QWidget(self._left_panel)
        tm_layout = QVBoxLayout(self._tm_panel)
        tm_layout.setContentsMargins(6, 0, 6, 6)
        tm_layout.setSpacing(6)
        self._tm_status_label = QLabel("Select a row to see TM suggestions.")
        tm_filter_row = QHBoxLayout()
        tm_filter_row.setContentsMargins(0, 0, 0, 0)
        tm_filter_row.setSpacing(6)
        tm_filter_row.addWidget(QLabel("Min score", self._tm_panel))
        self._tm_score_spin = QSpinBox(self._tm_panel)
        self._tm_score_spin.setRange(30, 100)
        self._tm_score_spin.setValue(self._tm_min_score)
        self._tm_score_spin.setSuffix("%")
        self._tm_score_spin.valueChanged.connect(self._on_tm_filters_changed)
        tm_filter_row.addWidget(self._tm_score_spin)
        tm_filter_row.addStretch(1)
        self._tm_origin_project_cb = QCheckBox("Project", self._tm_panel)
        self._tm_origin_project_cb.setChecked(self._tm_origin_project)
        self._tm_origin_project_cb.toggled.connect(self._on_tm_filters_changed)
        tm_filter_row.addWidget(self._tm_origin_project_cb)
        self._tm_origin_import_cb = QCheckBox("Imported", self._tm_panel)
        self._tm_origin_import_cb.setChecked(self._tm_origin_import)
        self._tm_origin_import_cb.toggled.connect(self._on_tm_filters_changed)
        tm_filter_row.addWidget(self._tm_origin_import_cb)
        self._tm_list = QListWidget(self._tm_panel)
        self._tm_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self._tm_list.itemSelectionChanged.connect(self._update_tm_apply_state)
        self._tm_list.itemDoubleClicked.connect(self._apply_tm_selection)
        self._tm_apply_btn = QPushButton("Apply", self._tm_panel)
        self._tm_apply_btn.setEnabled(False)
        self._tm_apply_btn.clicked.connect(self._apply_tm_selection)
        tm_layout.addWidget(self._tm_status_label)
        tm_layout.addLayout(tm_filter_row)
        tm_layout.addWidget(self._tm_list)
        tm_layout.addWidget(self._tm_apply_btn)
        self._left_stack.addWidget(self._tm_panel)

        self._search_panel = QWidget(self._left_panel)
        search_layout = QVBoxLayout(self._search_panel)
        search_layout.setContentsMargins(6, 0, 6, 6)
        search_layout.setSpacing(6)
        search_layout.addWidget(QLabel("Search results list not implemented yet."))
        self._left_stack.addWidget(self._search_panel)

        self._left_files_btn.setChecked(True)
        self._left_stack.setCurrentIndex(0)

        left_layout.addWidget(toggle_bar)
        left_layout.addWidget(self._left_stack)
        self._content_splitter.addWidget(self._left_panel)

        # ── status shortcuts ────────────────────────────────────────────────
        act_proof = QAction("&Mark Proofread", self)
        act_proof.setShortcut("Ctrl+P")
        act_proof.triggered.connect(self._mark_proofread)
        self.addAction(act_proof)
        self.act_proof = act_proof
        act_translated = QAction("Mark &Translated", self)
        act_translated.setShortcut("Ctrl+T")
        act_translated.triggered.connect(self._mark_translated)
        self.addAction(act_translated)
        self.act_translated = act_translated
        act_review = QAction("Mark &For Review", self)
        act_review.setShortcut("Ctrl+U")
        act_review.triggered.connect(self._mark_for_review)
        self.addAction(act_review)
        self.act_review = act_review

        # ── right pane: entry table ─────────────────────────────────────────
        self.table = QTableView()
        self.table.setSelectionBehavior(QAbstractItemView.SelectItems)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setWordWrap(self._wrap_text)
        self._default_row_height = max(20, self.table.fontMetrics().lineSpacing() + 8)
        self._apply_row_height_mode()
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.table.verticalScrollBar().valueChanged.connect(self._on_table_scrolled)
        self.table.viewport().setMouseTracking(True)
        self.table.viewport().installEventFilter(self)
        self._key_delegate = KeyDelegate(self.table)
        self.table.setItemDelegateForColumn(0, self._key_delegate)
        self._source_delegate = VisualTextDelegate(
            self.table,
            read_only=True,
            options_provider=self._text_visual_options_table,
        )
        self.table.setItemDelegateForColumn(1, self._source_delegate)
        self._value_delegate = VisualTextDelegate(
            self.table,
            read_only=False,
            options_provider=self._text_visual_options_table,
        )
        self.table.setItemDelegateForColumn(2, self._value_delegate)
        self._status_delegate = StatusDelegate(self.table)
        self.table.setItemDelegateForColumn(3, self._status_delegate)
        self.table.horizontalHeader().sectionResized.connect(self._on_header_resized)
        QToolTip.setFont(self.table.font())
        self._right_stack = QStackedWidget(self)
        self._table_container = QWidget(self)
        table_layout = QVBoxLayout(self._table_container)
        table_layout.setContentsMargins(0, 0, 0, 0)
        table_layout.addWidget(self.table)
        self._right_stack.addWidget(self._table_container)
        self._merge_container: QWidget | None = None
        self._content_splitter.addWidget(self._right_stack)

        self._detail_panel = QWidget(self)
        self._detail_panel.setMinimumHeight(0)
        self._detail_panel.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        detail_layout = QVBoxLayout(self._detail_panel)
        detail_layout.setContentsMargins(2, 2, 2, 2)
        detail_layout.setSpacing(2)
        self._detail_source_label = QLabel("Source", self._detail_panel)
        detail_layout.addWidget(self._detail_source_label)
        self._detail_source = _CommitPlainTextEdit(
            None,
            self._detail_panel,
            focus_cb=self._load_pending_detail_text,
        )
        self._detail_source.setReadOnly(True)
        self._detail_source.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        self._detail_source.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self._detail_source.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._detail_source.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        self._detail_source_highlighter = TextVisualHighlighter(
            self._detail_source.document(), self._text_visual_options_detail
        )
        line_height = self._detail_source.fontMetrics().lineSpacing()
        min_line_height = max(22, line_height + 6)
        self._detail_source.setMinimumHeight(min_line_height)
        detail_layout.addWidget(self._detail_source)
        self._detail_translation_label = QLabel("Translation", self._detail_panel)
        detail_layout.addWidget(self._detail_translation_label)
        self._detail_translation = _CommitPlainTextEdit(
            self._commit_detail_translation,
            self._detail_panel,
            focus_cb=self._load_pending_detail_text,
        )
        self._detail_translation.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        self._detail_translation.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self._detail_translation.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._detail_translation.setSizePolicy(
            QSizePolicy.Preferred, QSizePolicy.Minimum
        )
        self._detail_translation_highlighter = TextVisualHighlighter(
            self._detail_translation.document(), self._text_visual_options_detail
        )
        self._detail_translation.setMinimumHeight(min_line_height)
        self._detail_translation.textChanged.connect(
            self._on_detail_translation_changed
        )
        detail_layout.addWidget(self._detail_translation)
        margins = detail_layout.contentsMargins()
        label_total = (
            self._detail_source_label.sizeHint().height()
            + self._detail_translation_label.sizeHint().height()
        )
        self._detail_min_height = (
            margins.top()
            + margins.bottom()
            + label_total
            + min_line_height * 2
            + detail_layout.spacing() * 3
        )
        self._detail_panel.setVisible(False)
        self._main_splitter.addWidget(self._detail_panel)
        self._main_splitter.setStretchFactor(0, 1)
        self._main_splitter.setStretchFactor(1, 0)

        tree_width = self._initial_tree_width(lazy_tree)
        self._content_splitter.setSizes([tree_width, 980])
        self._main_splitter.setSizes([1, 0])
        self.resize(1200, 800)
        self.act_undo: QAction | None = None
        self.act_redo: QAction | None = None

        # ── undo/redo actions ───────────────────────────────────────────────

        # ── save action ─────────────────────────────────────────────────────
        act_save = QAction("&Save", self)
        act_save.setShortcut(QKeySequence.StandardKey.Save)
        act_save.triggered.connect(self._request_write_original)
        self.addAction(act_save)
        act_open = QAction("&Open", self)
        act_open.setShortcut(QKeySequence.StandardKey.Open)
        act_open.triggered.connect(self._open_project)
        self.addAction(act_open)
        act_switch = QAction("Switch &Locale(s)", self)
        act_switch.triggered.connect(self._switch_locales)
        self.addAction(act_switch)
        act_exit = QAction("E&xit", self)
        act_exit.setShortcut(QKeySequence.StandardKey.Quit)
        act_exit.triggered.connect(self.close)
        self.addAction(act_exit)
        act_prefs = QAction("&Preferences…", self)
        act_prefs.setShortcut(QKeySequence.StandardKey.Preferences)
        act_prefs.triggered.connect(self._open_preferences)
        self.addAction(act_prefs)
        self.menu_general.addAction(act_open)
        self.menu_general.addAction(act_save)
        self.menu_general.addAction(act_switch)
        self.menu_general.addSeparator()
        self.menu_general.addAction(act_prefs)
        self.menu_general.addSeparator()
        self.menu_general.addAction(act_exit)

        act_import_tmx = QAction("Import TMX…", self)
        act_import_tmx.triggered.connect(self._import_tmx)
        self.menu_tm.addAction(act_import_tmx)
        act_export_tmx = QAction("Export TMX…", self)
        act_export_tmx.triggered.connect(self._export_tmx)
        self.menu_tm.addAction(act_export_tmx)
        self.menu_tm.addSeparator()
        act_rebuild_tm = QAction("Rebuild Project TM (Selected Locales)", self)
        act_rebuild_tm.triggered.connect(self._rebuild_tm_selected)
        self.menu_tm.addAction(act_rebuild_tm)

        act_copy = QAction("&Copy", self)
        act_copy.setShortcut(QKeySequence.StandardKey.Copy)
        act_copy.triggered.connect(self._copy_selection)
        self.addAction(act_copy)
        act_cut = QAction("Cu&t", self)
        act_cut.setShortcut(QKeySequence.StandardKey.Cut)
        act_cut.triggered.connect(self._cut_selection)
        self.addAction(act_cut)
        act_paste = QAction("&Paste", self)
        act_paste.setShortcut(QKeySequence.StandardKey.Paste)
        act_paste.triggered.connect(self._paste_selection)
        self.addAction(act_paste)
        self.menu_edit.addAction(act_copy)
        self.menu_edit.addAction(act_cut)
        self.menu_edit.addAction(act_paste)
        act_find = QAction("&Find", self)
        act_find.setShortcut(QKeySequence.StandardKey.Find)
        act_find.triggered.connect(self._focus_search)
        self.addAction(act_find)
        act_find_next = QAction("Find &Next", self)
        act_find_next.setShortcut(QKeySequence.StandardKey.FindNext)
        act_find_next.triggered.connect(self._search_next)
        self.addAction(act_find_next)
        act_find_prev = QAction("Find &Previous", self)
        act_find_prev.setShortcut(QKeySequence.StandardKey.FindPrevious)
        act_find_prev.triggered.connect(self._search_prev)
        self.addAction(act_find_prev)

        act_wrap = QAction("Wrap &Long Strings", self)
        act_wrap.setCheckable(True)
        act_wrap.setChecked(self._wrap_text)
        act_wrap.triggered.connect(self._toggle_wrap_text)
        self.addAction(act_wrap)
        self.act_wrap = act_wrap
        act_prompt = QAction("Prompt on E&xit", self)
        act_prompt.setCheckable(True)
        act_prompt.setChecked(self._prompt_write_on_exit)
        act_prompt.triggered.connect(self._toggle_prompt_on_exit)
        self.addAction(act_prompt)
        self.menu_view.addAction(act_wrap)
        self.menu_view.addAction(act_prompt)
        act_about = QAction("&About", self)
        act_about.triggered.connect(self._show_about)
        self.addAction(act_about)
        self.menu_help.addAction(act_about)

        # ── cache ──────────────────────────────────────────────────────
        self.detail_toggle = QToolButton(self)
        self.detail_toggle.setCheckable(True)
        self.detail_toggle.setAutoRaise(True)
        self.detail_toggle.setText("")
        self.detail_toggle.setToolButtonStyle(Qt.ToolButtonIconOnly)
        self._update_detail_toggle(False)
        self.detail_toggle.toggled.connect(self._toggle_detail_panel)
        self.statusBar().addPermanentWidget(self.detail_toggle)
        self.detail_toggle.setChecked(True)
        (
            self._search_scope_widget,
            self._search_scope_action,
            self._search_scope_icon,
        ) = self._build_scope_indicator("edit-find", "Search scope")
        (
            self._replace_scope_widget,
            self._replace_scope_action,
            self._replace_scope_icon,
        ) = self._build_scope_indicator("edit-find-replace", "Replace scope")
        self.statusBar().addPermanentWidget(self._search_scope_widget)
        self.statusBar().addPermanentWidget(self._replace_scope_widget)
        self._update_status_bar()
        self._apply_text_visual_options()

    def _build_scope_indicator(self, icon_name: str, tooltip: str):
        widget = QWidget(self)
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.setSpacing(2)
        action = QLabel(widget)
        scope = QLabel(widget)
        layout.addWidget(action)
        layout.addWidget(scope)
        action.setPixmap(
            QIcon.fromTheme(
                icon_name,
                self.style().standardIcon(
                    QStyle.StandardPixmap.SP_FileDialogContentsView
                ),
            ).pixmap(14, 14)
        )
        widget.setVisible(False)
        widget.setToolTip(tooltip)
        return widget, action, scope

    def _update_detail_toggle(self, visible: bool) -> None:
        if visible:
            self.detail_toggle.setIcon(
                self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowDown)
            )
            self.detail_toggle.setToolTip("Hide string editor")
        else:
            self.detail_toggle.setIcon(
                self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowUp)
            )
            self.detail_toggle.setToolTip("Show string editor")

    def _toggle_detail_panel(self, checked: bool) -> None:
        min_height = max(70, self._detail_min_height)
        if checked:
            self._detail_panel.setVisible(True)
            self._main_splitter.setCollapsible(1, False)
            total = max(0, self._main_splitter.height())
            if self._detail_last_height is None:
                target = min_height * 2
            else:
                target = self._detail_last_height
            self._detail_panel.setMinimumHeight(min_height)
            height = min(max(min_height, target), max(min_height, total - 80))
            top = max(80, total - height)
            self._main_splitter.setSizes([top, height])
            QTimer.singleShot(0, lambda: self._main_splitter.setSizes([top, height]))
            self._sync_detail_editors()
        else:
            self._commit_detail_translation()
            if self._detail_panel.isVisible():
                self._detail_last_height = max(min_height, self._detail_panel.height())
            self._detail_panel.setVisible(False)
            self._main_splitter.setCollapsible(1, True)
            self._main_splitter.setSizes([1, 0])
        self._update_detail_toggle(checked)

    def _on_main_splitter_moved(self, _pos: int, _index: int) -> None:
        if not self._detail_panel.isVisible():
            return
        sizes = self._main_splitter.sizes()
        if len(sizes) >= 2:
            min_height = max(70, self._detail_min_height)
            self._detail_last_height = max(min_height, sizes[1])

    def _on_content_splitter_moved(self, _pos: int, _index: int) -> None:
        if not self.tree.isVisible():
            return
        sizes = self._content_splitter.sizes()
        if len(sizes) >= 2 and sizes[0] > 0:
            self._tree_last_width = max(60, sizes[0])
            self._schedule_tree_width_persist()

    def _schedule_tree_width_persist(self) -> None:
        if self._tree_width_timer.isActive():
            self._tree_width_timer.stop()
        self._tree_width_timer.start()

    def _persist_tree_width(self) -> None:
        self._prefs_extras["TREE_PANEL_WIDTH"] = str(max(60, self._tree_last_width))
        self._persist_preferences()

    def _toggle_tree_panel(self, checked: bool) -> None:
        if checked:
            sizes = self._content_splitter.sizes()
            if sizes:
                self._tree_last_width = max(60, sizes[0])
                self._schedule_tree_width_persist()
            self._left_panel.setVisible(False)
            self.tree_toggle.setIcon(
                self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowRight)
            )
            self.tree_toggle.setToolTip("Show side panel")
            total = max(0, self._content_splitter.width())
            if total <= 0 and sizes:
                total = sum(sizes)
            self._content_splitter.setSizes([0, max(100, total)])
        else:
            self._left_panel.setVisible(True)
            lazy_tree = bool(self.fs_model and self.fs_model.is_lazy())
            width = self._initial_tree_width(lazy_tree)
            sizes = self._content_splitter.sizes()
            total = max(0, self._content_splitter.width())
            if total <= 0 and sizes:
                total = sum(sizes)
            self._content_splitter.setSizes([width, max(100, total - width)])
            self.tree_toggle.setIcon(
                self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowLeft)
            )
            self.tree_toggle.setToolTip("Hide side panel")
        if self.table.model():
            self._apply_table_layout()

    def _on_detail_translation_changed(self) -> None:
        if self._detail_syncing:
            return
        self._detail_dirty = True

    def _commit_detail_translation(self, index=None) -> None:
        if not self._detail_dirty or not self._current_model:
            return
        if self._detail_pending_row is not None:
            return
        if not self._detail_panel.isVisible():
            self._detail_dirty = False
            return
        idx = (
            index
            if index is not None and index.isValid()
            else self.table.currentIndex()
        )
        if not idx.isValid():
            self._detail_dirty = False
            return
        model_index = self._current_model.index(idx.row(), 2)
        new_text = self._detail_translation.toPlainText()
        if model_index.data(Qt.EditRole) != new_text:
            self._current_model.setData(model_index, new_text, Qt.EditRole)
        self._detail_dirty = False

    def _load_pending_detail_text(self) -> None:
        if self._detail_pending_row is None or not self._detail_pending_active:
            return
        if not self._detail_panel.isVisible():
            return
        if not self._current_model:
            return
        idx = self.table.currentIndex()
        if not idx.isValid():
            return
        source_index = self._current_model.index(idx.row(), 1)
        value_index = self._current_model.index(idx.row(), 2)
        source_text = str(source_index.data(Qt.EditRole) or "")
        value_text = str(value_index.data(Qt.EditRole) or "")
        self._detail_syncing = True
        try:
            self._detail_translation.setReadOnly(False)
            self._detail_translation.setPlaceholderText("")
            self._detail_source.setPlaceholderText("")
            self._detail_source.setPlainText(source_text)
            self._detail_translation.setPlainText(value_text)
        finally:
            self._detail_syncing = False
        self._detail_dirty = False
        self._detail_pending_row = None
        self._detail_pending_active = False
        self._apply_detail_whitespace_options()

    def _set_detail_pending(self, row: int) -> None:
        self._detail_pending_row = row
        self._detail_pending_active = True
        self._detail_syncing = True
        try:
            # Avoid loading huge strings on selection; only load when editor is focused.
            self._detail_translation.setReadOnly(True)
            self._detail_source.setPlaceholderText(
                "Large text. Click to load full source."
            )
            self._detail_translation.setPlaceholderText(
                "Large text. Click to load full translation."
            )
            self._detail_source.setPlainText("")
            self._detail_translation.setPlainText("")
        finally:
            self._detail_syncing = False
        self._detail_dirty = False
        if self._detail_source.hasFocus() or self._detail_translation.hasFocus():
            self._load_pending_detail_text()

    def _sync_detail_editors(self) -> None:
        if not self._detail_panel.isVisible():
            return
        perf_trace = PERF_TRACE
        perf_start = perf_trace.start("detail_sync")
        try:
            if not self._current_model:
                self._detail_pending_row = None
                self._detail_pending_active = False
                self._detail_syncing = True
                try:
                    self._detail_source.setPlainText("")
                    self._detail_translation.setPlainText("")
                finally:
                    self._detail_syncing = False
                self._detail_dirty = False
                return
            idx = self.table.currentIndex()
            if not idx.isValid():
                self._detail_pending_row = None
                self._detail_pending_active = False
                self._detail_syncing = True
                try:
                    self._detail_source.setPlainText("")
                    self._detail_translation.setPlainText("")
                finally:
                    self._detail_syncing = False
                self._detail_dirty = False
                return
            # Length check avoids forcing lazy decode for huge strings on selection.
            source_len, value_len = self._current_model.text_lengths(idx.row())
            if (
                self._large_text_optimizations
                and max(source_len, value_len) >= _DETAIL_LAZY_THRESHOLD
            ):
                self._set_detail_pending(idx.row())
                return
            source_index = self._current_model.index(idx.row(), 1)
            value_index = self._current_model.index(idx.row(), 2)
            source_text = str(source_index.data(Qt.EditRole) or "")
            value_text = str(value_index.data(Qt.EditRole) or "")
            self._detail_pending_row = None
            self._detail_pending_active = False
            self._detail_syncing = True
            try:
                self._detail_translation.setReadOnly(False)
                self._detail_translation.setPlaceholderText("")
                self._detail_source.setPlainText(source_text)
                self._detail_translation.setPlainText(value_text)
            finally:
                self._detail_syncing = False
            self._detail_dirty = False
            self._apply_detail_whitespace_options()
        finally:
            perf_trace.stop("detail_sync", perf_start, items=1, unit="events")

    def _scope_icon(self, scope: str) -> QIcon:
        if scope == "FILE":
            return QIcon.fromTheme(
                "text-x-generic",
                self.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon),
            )
        if scope == "LOCALE":
            return QIcon.fromTheme(
                "folder", self.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon)
            )
        return QIcon.fromTheme(
            "view-list-tree",
            self.style().standardIcon(QStyle.StandardPixmap.SP_DirOpenIcon),
        )

    def _init_locales(self, selected_locales: list[str] | None) -> None:
        try:
            self._locales, errors = scan_root_with_errors(self._root)
        except Exception as exc:
            QMessageBox.critical(self, "Invalid language.txt", str(exc))
            self._locales = {}
            self._selected_locales = []
            return
        if errors:
            msg = QMessageBox(self)
            msg.setIcon(QMessageBox.Warning)
            msg.setWindowTitle("Malformed language.txt")
            msg.setText(
                "Some locales were skipped due to malformed language.txt. "
                "Fix those files to enable the locales."
            )
            msg.setDetailedText("\n".join(errors))
            msg.exec()
        self._schedule_cache_migration()
        selectable = {k: v for k, v in self._locales.items() if k != "EN"}
        self._files_by_locale.clear()

        if not selectable and selected_locales is None:
            self._selected_locales = []
            return

        if selected_locales is None and self._smoke:
            if self._last_locales:
                selected_locales = list(self._last_locales)
            elif selectable:
                selected_locales = [next(iter(selectable.keys()))]
            else:
                selected_locales = []
        if selected_locales is None:
            dialog = LocaleChooserDialog(
                selectable.values(), self, preselected=self._last_locales
            )
            if dialog.exec() != dialog.DialogCode.Accepted:
                self._selected_locales = []
                return
            selected_locales = dialog.selected_codes()

        self._selected_locales = [c for c in selected_locales if c in selectable]
        self._tm_bootstrap_pending = bool(self._selected_locales)
        QTimer.singleShot(0, self._warn_orphan_caches)
        self._schedule_post_locale_tasks()

    def _init_tm_store(self) -> None:
        try:
            self._tm_store = TMStore(self._root)
        except Exception as exc:
            self._tm_store = None
            QMessageBox.warning(self, "TM init failed", str(exc))

    def _ensure_tm_store(self) -> bool:
        if self._tm_store is None:
            self._init_tm_store()
        if self._tm_store is None:
            return False
        if self._tm_query_pool is None:
            self._tm_query_pool = ThreadPoolExecutor(
                max_workers=1, thread_name_prefix="tzp-tm"
            )
        return True

    def _locale_for_path(self, path: Path) -> str | None:
        try:
            rel = path.relative_to(self._root)
        except ValueError:
            return None
        if not rel.parts:
            return None
        return rel.parts[0]

    def _en_path_for(self, path: Path, locale: str | None) -> Path | None:
        if not locale or locale == "EN":
            return None
        en_meta = self._locales.get("EN")
        if not en_meta:
            return None
        try:
            rel = path.relative_to(self._root / locale)
        except ValueError:
            try:
                rel_full = path.relative_to(self._root)
                if rel_full.parts and rel_full.parts[0] == locale:
                    rel = Path(*rel_full.parts[1:])
                else:
                    return None
            except ValueError:
                return None
        candidate = en_meta.path / rel
        if candidate.exists():
            return candidate
        stem = rel.stem
        for token in (locale, locale.replace(" ", "_")):
            suffix = f"_{token}"
            if stem.endswith(suffix):
                new_stem = stem[: -len(suffix)] + "_EN"
                alt = rel.with_name(new_stem + rel.suffix)
                alt_path = en_meta.path / alt
                if alt_path.exists():
                    return alt_path
        return None

    def _load_en_source(
        self,
        path: Path,
        locale: str | None,
        *,
        target_entries: Sequence[Entry] | None = None,
    ) -> _SourceLookup:
        def _key_at(entries: Sequence[Entry], idx: int) -> str:
            if hasattr(entries, "key_at"):
                return entries.key_at(idx)
            return entries[idx].key

        def _keys_match(a: Sequence[Entry], b: Sequence[Entry]) -> bool:
            count = len(a)
            if count != len(b):
                return False
            return all(_key_at(a, idx) == _key_at(b, idx) for idx in range(count))

        def _keys_list(entries: Sequence[Entry]) -> list[str]:
            return [_key_at(entries, idx) for idx in range(len(entries))]

        en_path = self._en_path_for(path, locale)
        if not en_path:
            return _SourceLookup(by_key={})
        if en_path in self._en_cache:
            pf = self._en_cache[en_path]
        else:
            en_meta = self._locales.get("EN")
            encoding = en_meta.charset if en_meta else "utf-8"
            try:
                if self._should_parse_lazy(en_path):
                    pf = parse_lazy(en_path, encoding=encoding)
                else:
                    pf = parse(en_path, encoding=encoding)
            except Exception:
                return _SourceLookup(by_key={})
            self._en_cache[en_path] = pf
        entries = pf.entries
        if entries:
            if hasattr(entries, "meta_at"):
                if len(entries) == 1 and entries.meta_at(0).raw:
                    raw_value = entries[0].value
                    if (
                        target_entries
                        and len(target_entries) == 1
                        and _key_at(target_entries, 0) == path.name
                    ):
                        return _SourceLookup(by_row=[raw_value], keys=[path.name])
                    return _SourceLookup(by_key={path.name: raw_value})
            elif all(getattr(e, "raw", False) for e in entries):
                raw_value = entries[0].value
                if (
                    target_entries
                    and len(target_entries) == 1
                    and _key_at(target_entries, 0) == path.name
                ):
                    return _SourceLookup(by_row=[raw_value], keys=[path.name])
                return _SourceLookup(by_key={path.name: raw_value})
        if target_entries and _keys_match(target_entries, entries):
            keys = _keys_list(target_entries)
            if hasattr(entries, "prefetch"):
                return _SourceLookup(by_row=_LazySourceRows(entries), keys=keys)
            by_row = [entry.value for entry in entries]
            return _SourceLookup(by_row=by_row, keys=keys)
        return _SourceLookup(by_key={entry.key: entry.value for entry in entries})

    # ----------------------------------------------------------------- slots
    def _check_en_hash_cache(self) -> bool:
        try:
            computed = _compute_en_hashes(self._root)
        except Exception:
            return True
        if not computed:
            return True
        cached = _read_en_hash_cache(self._root)
        if not cached:
            _write_en_hash_cache(self._root, computed)
            return True
        if cached == computed:
            return True
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Warning)
        msg.setWindowTitle("English source changed")
        msg.setText("English reference files have changed.")
        msg.setInformativeText(
            "Please update translations accordingly. "
            "Continue to reset the reminder, or Dismiss to be reminded later."
        )
        ack = msg.addButton("Continue", QMessageBox.AcceptRole)
        msg.addButton("Dismiss", QMessageBox.RejectRole)
        msg.exec()
        if msg.clickedButton() is ack:
            _write_en_hash_cache(self._root, computed)
        return True

    def _prompt_write_original(self) -> str:
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Question)
        msg.setWindowTitle("Write to original file")
        msg.setText("Write draft translations to the original file?")
        msg.setInformativeText("No keeps changes in cache only.")
        msg.setStandardButtons(
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No
            | QMessageBox.StandardButton.Cancel
        )
        result = msg.exec()
        if result == QMessageBox.StandardButton.Yes:
            return "yes"
        if result == QMessageBox.StandardButton.No:
            return "no"
        return "cancel"

    def _open_project(self) -> None:
        start_dir = self._last_root or str(self._root)
        picked = QFileDialog.getExistingDirectory(self, "Open Project", start_dir)
        if not picked:
            return
        win = MainWindow(picked)
        if getattr(win, "_startup_aborted", False):
            return
        win.show()
        self._child_windows.append(win)

    def _import_tmx(self) -> None:
        if not self._ensure_tm_store():
            QMessageBox.warning(self, "TM unavailable", "TM store is not available.")
            return
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Import TMX",
            str(self._root),
            "TMX files (*.tmx);;All files (*)",
        )
        if not path:
            return
        from translationzed_py.core.tmx_io import detect_tmx_languages

        langs = detect_tmx_languages(Path(path))
        default_target = None
        if self._current_pf:
            default_target = self._locale_for_path(self._current_pf.path)
        dialog = TmLanguageDialog(
            langs,
            parent=self,
            default_source=self._tm_source_locale,
            default_target=default_target,
            title="Import TMX",
        )
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        source_locale = dialog.source_locale()
        target_locale = dialog.target_locale()
        if not source_locale or not target_locale:
            QMessageBox.warning(
                self, "Invalid locales", "Source/target locales required."
            )
            return
        try:
            count = self._tm_store.import_tmx(
                Path(path), source_locale=source_locale, target_locale=target_locale
            )
        except Exception as exc:
            QMessageBox.warning(self, "TMX import failed", str(exc))
            return
        self._tm_cache.clear()
        QMessageBox.information(
            self,
            "TMX import complete",
            f"Imported {count} translation unit(s).",
        )

    def _export_tmx(self) -> None:
        if not self._ensure_tm_store():
            QMessageBox.warning(self, "TM unavailable", "TM store is not available.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export TMX",
            str(self._root / "translation_memory.tmx"),
            "TMX files (*.tmx);;All files (*)",
        )
        if not path:
            return
        languages = sorted(self._locales.keys())
        default_target = None
        if self._current_pf:
            default_target = self._locale_for_path(self._current_pf.path)
        dialog = TmLanguageDialog(
            languages,
            parent=self,
            default_source=self._tm_source_locale,
            default_target=default_target,
            title="Export TMX",
        )
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        source_locale = dialog.source_locale()
        target_locale = dialog.target_locale()
        if not source_locale or not target_locale:
            QMessageBox.warning(
                self, "Invalid locales", "Source/target locales required."
            )
            return
        try:
            count = self._tm_store.export_tmx(
                Path(path), source_locale=source_locale, target_locale=target_locale
            )
        except Exception as exc:
            QMessageBox.warning(self, "TMX export failed", str(exc))
            return
        QMessageBox.information(
            self,
            "TMX export complete",
            f"Exported {count} translation unit(s).",
        )

    def _rebuild_tm_selected(self) -> None:
        if not self._tm_store:
            QMessageBox.warning(self, "TM unavailable", "TM store is not available.")
            return
        locales = [loc for loc in self._selected_locales if loc != "EN"]
        if not locales:
            QMessageBox.information(self, "TM rebuild", "No locales selected.")
            return
        self._start_tm_rebuild(locales, interactive=True, force=True)

    def _maybe_bootstrap_tm(self) -> None:
        if self._test_mode or not self._ensure_tm_store():
            return
        if not self._selected_locales:
            return
        locales: list[str] = []
        for loc in self._selected_locales:
            if loc == "EN":
                continue
            try:
                has_entries = self._tm_store.has_entries(
                    source_locale=self._tm_source_locale, target_locale=loc
                )
            except Exception:
                continue
            if not has_entries:
                locales.append(loc)
        if not locales:
            return
        self._start_tm_rebuild(locales, interactive=False, force=False)

    def _collect_tm_rebuild_locales(
        self, locales: Iterable[str]
    ) -> tuple[list[_TMRebuildLocale], str]:
        en_meta = self._locales.get("EN")
        en_encoding = en_meta.charset if en_meta else "utf-8"
        out: list[_TMRebuildLocale] = []
        for locale in locales:
            if locale == "EN":
                continue
            meta = self._locales.get(locale)
            if not meta:
                continue
            out.append((locale, meta.path, meta.charset))
        return out, en_encoding

    def _start_tm_rebuild(
        self, locales: Iterable[str], *, interactive: bool, force: bool
    ) -> None:
        if not self._tm_store:
            return
        if (
            self._tm_rebuild_future is not None
            and not self._tm_rebuild_future.done()
        ):
            self.statusBar().showMessage("TM rebuild already running.", 3000)
            return
        locale_specs, en_encoding = self._collect_tm_rebuild_locales(locales)
        if not locale_specs:
            if interactive:
                QMessageBox.information(self, "TM rebuild", "No TM entries found.")
            return
        if self._tm_rebuild_pool is None:
            self._tm_rebuild_pool = ThreadPoolExecutor(
                max_workers=1, thread_name_prefix="tzp-tm-rebuild"
            )
        self._tm_rebuild_locales = sorted({entry[0] for entry in locale_specs})
        self._tm_rebuild_interactive = interactive
        label = ", ".join(self._tm_rebuild_locales)
        prefix = "Rebuilding TM" if force else "Bootstrapping TM"
        self.statusBar().showMessage(f"{prefix} for {label}…", 0)
        self._tm_rebuild_future = self._tm_rebuild_pool.submit(
            _tm_rebuild_worker,
            self._root,
            locale_specs,
            self._tm_source_locale,
            en_encoding,
        )
        if not self._tm_rebuild_timer.isActive():
            self._tm_rebuild_timer.start()

    def _poll_tm_rebuild(self) -> None:
        future = self._tm_rebuild_future
        if future is None:
            self._tm_rebuild_timer.stop()
            return
        if not future.done():
            return
        self._tm_rebuild_timer.stop()
        self._tm_rebuild_future = None
        try:
            result = future.result()
        except Exception as exc:
            message = f"TM rebuild failed: {exc}"
            if self._tm_rebuild_interactive:
                QMessageBox.warning(self, "TM rebuild failed", message)
            else:
                self.statusBar().showMessage(message, 5000)
            return
        self._finish_tm_rebuild(result)

    def _finish_tm_rebuild(self, result: dict[str, int]) -> None:
        self._tm_cache.clear()
        total_missing = result.get("skipped_missing_source", 0)
        parts = [
            f"TM rebuild complete: {result.get('entries', 0)} entries",
            f"{result.get('files', 0)} files",
        ]
        skipped = []
        if total_missing:
            skipped.append(f"missing source {total_missing}")
        if result.get("skipped_parse"):
            skipped.append(f"parse errors {result['skipped_parse']}")
        if result.get("skipped_empty"):
            skipped.append(f"empty values {result['skipped_empty']}")
        if skipped:
            parts.append(f"skipped {', '.join(skipped)}")
        message = " · ".join(parts)
        self.statusBar().showMessage(message, 8000)
        if self._left_stack.currentIndex() == 1:
            self._update_tm_suggestions()

    def _open_preferences(self) -> None:
        prefs = {
            "default_root": self._default_root,
            "prompt_write_on_exit": self._prompt_write_on_exit,
            "wrap_text": self._wrap_text_user,
            "large_text_optimizations": self._large_text_optimizations,
            "visual_highlight": self._visual_highlight,
            "visual_whitespace": self._visual_whitespace,
            "search_scope": self._search_scope,
            "replace_scope": self._replace_scope,
        }
        dialog = PreferencesDialog(prefs, parent=self)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        self._apply_preferences(dialog.values())

    def _show_about(self) -> None:
        dialog = AboutDialog(self)
        dialog.exec()

    def _apply_preferences(self, values: dict) -> None:
        self._prompt_write_on_exit = bool(values.get("prompt_write_on_exit", True))
        self._wrap_text_user = bool(values.get("wrap_text", False))
        large_text_opt = bool(
            values.get("large_text_optimizations", self._large_text_optimizations)
        )
        if large_text_opt != self._large_text_optimizations:
            self._large_text_optimizations = large_text_opt
            self._update_large_file_mode()
        self._apply_wrap_mode()
        visual_highlight = bool(values.get("visual_highlight", self._visual_highlight))
        visual_whitespace = bool(
            values.get("visual_whitespace", self._visual_whitespace)
        )
        if (
            visual_highlight != self._visual_highlight
            or visual_whitespace != self._visual_whitespace
        ):
            self._visual_highlight = visual_highlight
            self._visual_whitespace = visual_whitespace
            self._prefs_extras["TEXT_HIGHLIGHT"] = (
                "true" if self._visual_highlight else "false"
            )
            self._prefs_extras["TEXT_SHOW_WHITESPACE"] = (
                "true" if self._visual_whitespace else "false"
            )
            self._apply_text_visual_options()
        self._default_root = str(values.get("default_root", "")).strip()
        search_scope = str(values.get("search_scope", "FILE")).upper()
        if search_scope not in {"FILE", "LOCALE", "POOL"}:
            search_scope = "FILE"
        replace_scope = str(values.get("replace_scope", "FILE")).upper()
        if replace_scope not in {"FILE", "LOCALE", "POOL"}:
            replace_scope = "FILE"
        if search_scope != self._search_scope:
            self._search_scope = search_scope
            if self.search_edit.text():
                self._schedule_search()
        self._replace_scope = replace_scope
        self._persist_preferences()
        self._update_replace_enabled()
        self._update_status_bar()

    def _switch_locales(self) -> None:
        if not self._write_cache_current():
            return
        selectable = {k: v for k, v in self._locales.items() if k != "EN"}
        dialog = LocaleChooserDialog(
            selectable.values(), self, preselected=self._selected_locales
        )
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        selected = [c for c in dialog.selected_codes() if c in selectable]
        if not selected:
            return
        self._selected_locales = selected
        self._files_by_locale.clear()
        self._opened_files.clear()
        self._conflict_files.clear()
        self._conflict_sources.clear()
        self._conflict_notified.clear()
        self._current_pf = None
        self._current_model = None
        self.table.setModel(None)
        self._set_status_combo(None)
        lazy_tree = len(self._selected_locales) > 1
        self.fs_model = FsModel(
            self._root,
            [self._locales[c] for c in self._selected_locales],
            lazy=lazy_tree,
        )
        self.tree.setModel(self.fs_model)
        if self.fs_model.is_lazy():
            if len(self._selected_locales) == 1:
                idx = self.fs_model.index(0, 0)
                if idx.isValid():
                    self.fs_model.ensure_loaded_for_index(idx)
                    self.tree.expand(idx)
        else:
            self.tree.expandAll()
        tree_width = self._initial_tree_width(lazy_tree)
        sizes = self._content_splitter.sizes()
        total = max(0, self._content_splitter.width())
        if total <= 0 and sizes:
            total = sum(sizes)
        if total > 0:
            self._content_splitter.setSizes([tree_width, max(100, total - tree_width)])
        self._tm_bootstrap_pending = bool(self._selected_locales)
        self._schedule_post_locale_tasks()

    def _file_chosen(self, index) -> None:
        """Populate table when user activates a translation file."""
        raw_path = index.data(Qt.UserRole)  # FsModel stores absolute path string
        path = Path(raw_path) if raw_path else None
        if not (path and path.suffix == self._app_config.translation_ext):
            return
        if (
            self._current_pf
            and self._current_pf.path == path
            and not self._skip_cache_write
        ):
            return
        self._conflict_notified.discard(path)
        if self._skip_cache_write:
            self._skip_cache_write = False
        else:
            if not self._write_cache_current():
                return
        locale = self._locale_for_path(path)
        encoding = self._locales.get(
            locale, LocaleMeta("", Path(), "", "utf-8")
        ).charset
        try:
            if self._should_parse_lazy(path):
                pf = parse_lazy(path, encoding=encoding)
            else:
                pf = parse(path, encoding=encoding)
        except Exception as exc:
            self._report_parse_error(path, exc)
            return

        self._current_encoding = encoding
        try:
            self._current_file_size = path.stat().st_size
        except OSError:
            self._current_file_size = 0

        source_lookup = self._load_en_source(path, locale, target_entries=pf.entries)
        self._cache_map = _read_status_cache(self._root, path)
        _touch_last_opened(self._root, path, int(time.time()))
        changed_keys: set[str] = set()
        baseline_by_row: dict[int, str] = {}
        conflict_originals: dict[str, str] = {}
        original_values: dict[str, str] = {}
        if self._cache_map:
            if hasattr(pf.entries, "index_by_hash") and hasattr(pf.entries, "meta_at"):
                entries = pf.entries
                hash_bits = getattr(self._cache_map, "hash_bits", 64)
                index_by_hash = entries.index_by_hash(bits=hash_bits)
                for key_hash, rec in self._cache_map.items():
                    indices = index_by_hash.get(key_hash)
                    if not indices:
                        continue
                    for idx in indices:
                        meta = entries.meta_at(idx)
                        file_value = entries[idx].value
                        if (
                            rec.value is not None
                            and rec.original is not None
                            and rec.original != file_value
                        ):
                            conflict_originals[meta.key] = file_value
                        new_value = rec.value if rec.value is not None else file_value
                        if rec.value is not None and rec.value != file_value:
                            changed_keys.add(meta.key)
                            baseline_by_row[idx] = file_value
                            original_values[meta.key] = (
                                rec.original if rec.original is not None else file_value
                            )
                        if new_value != file_value or rec.status != meta.status:
                            entries[idx] = Entry(
                                meta.key,
                                new_value,
                                rec.status,
                                meta.span,
                                meta.segments,
                                meta.gaps,
                                meta.raw,
                                meta.key_hash,
                            )
            else:
                for idx, e in enumerate(pf.entries):
                    h = self._hash_for_cache(e, self._cache_map)
                    if h not in self._cache_map:
                        continue
                    rec = self._cache_map[h]
                    if (
                        rec.value is not None
                        and rec.original is not None
                        and rec.original != e.value
                    ):
                        conflict_originals[e.key] = e.value
                    new_value = rec.value if rec.value is not None else e.value
                    if rec.value is not None and rec.value != e.value:
                        changed_keys.add(e.key)
                        baseline_by_row[idx] = e.value
                        if rec.original is not None:
                            original_values[e.key] = rec.original
                        else:
                            original_values[e.key] = e.value
                    if new_value != e.value or rec.status != e.status:
                        pf.entries[idx] = type(e)(
                            e.key,
                            new_value,
                            rec.status,
                            e.span,
                            e.segments,
                            e.gaps,
                            e.raw,
                            getattr(e, "key_hash", None),
                        )
        self._current_pf = pf
        self._opened_files.add(path)
        if self._current_model:
            try:
                self._current_model.dataChanged.disconnect(self._on_model_changed)
                self._current_model.dataChanged.disconnect(self._on_model_data_changed)
            except (TypeError, RuntimeError):
                pass
        self._current_model = TranslationModel(
            pf,
            baseline_by_row=baseline_by_row,
            source_values=source_lookup,
            source_by_row=source_lookup.by_row,
        )
        self._current_model.dataChanged.connect(self._on_model_changed)
        self._current_model.dataChanged.connect(self._on_model_data_changed)
        if not self._user_resized_columns:
            self._source_translation_ratio = 0.5
        self._table_layout_guard = True
        self.table.setModel(self._current_model)
        self._clear_row_height_cache()
        self._apply_table_layout()
        self._table_layout_guard = False
        self._update_large_file_mode()
        self.table.selectionModel().currentChanged.connect(self._on_selection_changed)
        self._update_status_combo_from_selection()
        self._update_replace_enabled()
        self._sync_detail_editors()
        self._update_status_bar()
        if not self._last_saved_text:
            self._last_saved_text = "Ready"
            self._update_status_bar()
        if self._should_defer_post_open():
            self._schedule_post_open_tasks(path)
        else:
            self._prefetch_visible_rows()
            if self._wrap_text:
                self._schedule_row_resize()
        if changed_keys:
            self.fs_model.set_dirty(self._current_pf.path, True)
        if not self._skip_conflict_check:
            if conflict_originals:
                conflict_sources = {
                    key: source_lookup.get(key, "") for key in conflict_originals
                }
                self._register_conflicts(path, conflict_originals, conflict_sources)
            else:
                self._clear_conflicts(path)
        else:
            self._skip_conflict_check = False

        if self._cache_map and getattr(self._cache_map, "hash_bits", 64) == 16:
            try:
                _write_status_cache(
                    self._root,
                    path,
                    pf.entries,
                    changed_keys=changed_keys,
                    original_values=original_values,
                    last_opened=int(time.time()),
                )
            except Exception as exc:
                QMessageBox.warning(self, "Cache migration failed", str(exc))

        # (re)create undo/redo actions bound to this file’s stack
        for action in list(self.menu_edit.actions()):
            text = action.text().replace("&", "").strip()
            if text.startswith("Undo") or text.startswith("Redo"):
                self.menu_edit.removeAction(action)
        for old in (self.act_undo, self.act_redo):
            if old and isValid(old):
                try:
                    if old in self.menu_edit.actions():
                        self.menu_edit.removeAction(old)
                    self.removeAction(old)
                    old.deleteLater()
                except RuntimeError:
                    pass
        self.act_undo = None
        self.act_redo = None
        stack = self._current_model.undo_stack
        self.act_undo = stack.createUndoAction(self, "&Undo")
        self.act_redo = stack.createRedoAction(self, "&Redo")
        self.act_undo.setShortcut(QKeySequence.StandardKey.Undo)
        self.act_redo.setShortcut(QKeySequence("Ctrl+Y"))
        self.act_undo.setShortcutContext(Qt.ApplicationShortcut)
        self.act_redo.setShortcutContext(Qt.ApplicationShortcut)
        for a in (self.act_undo, self.act_redo):
            self.addAction(a)
        if self.menu_edit.actions():
            first = self.menu_edit.actions()[0]
            self.menu_edit.insertAction(first, self.act_redo)
            self.menu_edit.insertAction(first, self.act_undo)
        else:
            self.menu_edit.addAction(self.act_undo)
            self.menu_edit.addAction(self.act_redo)

    def _apply_table_layout(self) -> None:
        if not self.table.model():
            return
        perf_trace = PERF_TRACE
        perf_start = perf_trace.start("layout")
        header = self.table.horizontalHeader()
        header.setStretchLastSection(False)
        if self._key_column_width is None:
            self._key_column_width = 120
        if self._status_column_width is None:
            metrics = self.table.fontMetrics()
            labels = [st.label() for st in STATUS_ORDER]
            max_label = max(labels, key=metrics.horizontalAdvance)
            self._status_column_width = metrics.horizontalAdvance(max_label) + 24
        key_width = int(self._key_column_width or 0)
        status_width = int(self._status_column_width or 0)
        viewport_width = max(0, self.table.viewport().width())
        min_content = 90
        available = max(0, viewport_width - key_width - status_width)
        if viewport_width and available < min_content * 2:
            shrink = min_content * 2 - available
            if shrink > 0:
                key_width = max(80, key_width - shrink)
                available = max(0, viewport_width - key_width - status_width)
        ratio = self._source_translation_ratio or 0.5
        source_width = int(round(available * ratio))
        translation_width = max(0, available - source_width)
        self._table_layout_guard = True
        try:
            header.setSectionResizeMode(0, QHeaderView.Interactive)
            header.resizeSection(0, key_width)
            header.setSectionResizeMode(3, QHeaderView.Interactive)
            header.resizeSection(3, status_width)
            header.setSectionResizeMode(1, QHeaderView.Interactive)
            header.setSectionResizeMode(2, QHeaderView.Interactive)
            header.resizeSection(1, source_width)
            header.resizeSection(2, translation_width)
        finally:
            self._table_layout_guard = False
        self._prefs_extras["TABLE_KEY_WIDTH"] = str(key_width)
        self._prefs_extras["TABLE_STATUS_WIDTH"] = str(status_width)
        self._prefs_extras["TABLE_SRC_RATIO"] = f"{ratio:.6f}"
        perf_trace.stop("layout", perf_start, items=1, unit="events")

    def _is_large_file(self) -> bool:
        return bool(
            self._current_model
            and (
                self._current_model.rowCount() >= self._large_file_row_threshold
                or self._current_file_size >= self._large_file_bytes_threshold
            )
        )

    def _should_parse_lazy(self, path: Path) -> bool:
        try:
            return path.stat().st_size >= self._lazy_parse_min_bytes
        except OSError:
            return False

    def _visible_row_span(self) -> tuple[int, int] | None:
        if not self._current_model:
            return None
        total = self._current_model.rowCount()
        if total <= 0:
            return None
        viewport = self.table.viewport()
        if viewport is None:
            return None
        first = self.table.rowAt(0)
        last = self.table.rowAt(max(0, viewport.height() - 1))
        if first < 0:
            first = 0
        if last < 0:
            last = total - 1
        visible = max(1, last - first + 1)
        margin = max(2, int(visible * self._row_cache_margin_pct))
        start = max(0, first - margin)
        end = min(total - 1, last + margin)
        return start, end

    def _prefetch_visible_rows(self) -> None:
        if not self._current_model:
            return
        span = self._visible_row_span()
        if not span:
            return
        start, end = span
        margin = self._lazy_row_prefetch_margin
        if self._is_large_file():
            margin = min(margin, 50)
        start = max(0, start - margin)
        end = min(self._current_model.rowCount() - 1, end + margin)
        self._current_model.prefetch_rows(start, end)

    def _should_defer_post_open(self) -> bool:
        return self._is_large_file()

    def _schedule_post_open_tasks(self, path: Path) -> None:
        def _run() -> None:
            if not self._current_pf or self._current_pf.path != path:
                return
            self._prefetch_visible_rows()
            if self._wrap_text:
                self._schedule_row_resize()

        QTimer.singleShot(0, _run)

    def _schedule_row_resize(self, *, full: bool = False) -> None:
        if not self._wrap_text or not self._current_model:
            return
        span = self._visible_row_span()
        if not span:
            return
        self._pending_row_span = span
        if self._scrolling:
            return
        if self._row_resize_timer.isActive():
            self._row_resize_timer.stop()
        self._row_resize_timer.start()

    def _row_height_cache_signature(self) -> tuple[int, ...]:
        model = self.table.model()
        if model is None:
            return ()
        header = self.table.horizontalHeader()
        return tuple(header.sectionSize(i) for i in range(model.columnCount()))

    def _clear_row_height_cache(self, rows: Iterable[int] | None = None) -> None:
        if rows is None:
            self._row_height_cache.clear()
            self._row_height_cache_key = None
            return
        for row in rows:
            self._row_height_cache.pop(row, None)

    def _resize_visible_rows(self) -> None:
        if not self._wrap_text or not self._current_model:
            return
        span = self._pending_row_span or self._visible_row_span()
        if not span:
            return
        signature = self._row_height_cache_signature()
        if signature != self._row_height_cache_key:
            self._row_height_cache_key = signature
            self._row_height_cache.clear()
        start, end = span
        perf_trace = PERF_TRACE
        perf_start = perf_trace.start("row_resize")
        rows_processed = 0
        for row in range(start, end + 1):
            rows_processed += 1
            cached = self._row_height_cache.get(row)
            if cached is not None:
                if self.table.rowHeight(row) != cached:
                    self.table.setRowHeight(row, cached)
                continue
            height = self.table.sizeHintForRow(row)
            if height <= 0:
                continue
            self._row_height_cache[row] = height
            self.table.setRowHeight(row, height)
        self._pending_row_span = None
        perf_trace.stop("row_resize", perf_start, items=rows_processed, unit="rows")

    def _on_table_scrolled(self, *_args) -> None:
        self._prefetch_pending = True
        if not self._wrap_text:
            return
        self._scrolling = True
        if self._scroll_idle_timer.isActive():
            self._scroll_idle_timer.stop()
        self._scroll_idle_timer.start()

    def _on_scroll_idle(self) -> None:
        self._scrolling = False
        if self._prefetch_pending:
            self._prefetch_pending = False
            self._prefetch_visible_rows()
        if self._wrap_text:
            self._schedule_row_resize()

    def _on_tree_expanded(self, index: QModelIndex) -> None:
        if self.fs_model:
            self.fs_model.ensure_loaded_for_index(index)

    def _initial_tree_width(self, lazy_tree: bool) -> int:
        width = max(80, self._tree_last_width)
        if not lazy_tree:
            return width
        hint = self.tree.sizeHintForColumn(0)
        width = min(width, max(140, hint + 24)) if hint > 0 else min(width, 200)
        return width

    def _on_left_panel_changed(self, button) -> None:
        idx = self._left_group.id(button)
        if idx >= 0:
            self._left_stack.setCurrentIndex(idx)
        if idx == 1 and self._ensure_tm_store():
            if self._tm_bootstrap_pending:
                self._tm_bootstrap_pending = False
                self._maybe_bootstrap_tm()
            self._schedule_tm_update()

    def eventFilter(self, obj, event) -> bool:  # noqa: N802
        if obj is self.table.viewport():
            if event.type() == QEvent.MouseMove:
                idx = self.table.indexAt(event.pos())
                if not idx.isValid():
                    self._tooltip_timer.stop()
                    self._tooltip_index = QModelIndex()
                    QToolTip.hideText()
                    return False
                if idx != self._tooltip_index:
                    self._tooltip_index = idx
                    self._tooltip_pos = event.globalPos()
                    self._tooltip_timer.start()
                    QToolTip.hideText()
                else:
                    self._tooltip_pos = event.globalPos()
                return False
            if event.type() == QEvent.Leave:
                self._tooltip_timer.stop()
                self._tooltip_index = QModelIndex()
                QToolTip.hideText()
                return False
            if event.type() == QEvent.ToolTip:
                return True
        return super().eventFilter(obj, event)

    def _show_delayed_tooltip(self) -> None:
        idx = self._tooltip_index
        if not idx.isValid() or not self.table.model():
            return
        pos = self.table.viewport().mapFromGlobal(QCursor.pos())
        current = self.table.indexAt(pos)
        if not current.isValid() or current != idx:
            return
        text = self.table.model().data(idx, Qt.ToolTipRole)
        if not text:
            return
        tooltip = self._tooltip_html(str(text))
        QToolTip.showText(
            self._tooltip_pos,
            tooltip,
            self.table,
            self.table.visualRect(idx),
        )

    def _on_header_resized(self, logical_index: int, _old: int, _new: int) -> None:
        if self._table_layout_guard or not self.table.model():
            return
        if logical_index == 0:
            self._key_column_width = max(60, _new)
            self._prefs_extras["TABLE_KEY_WIDTH"] = str(self._key_column_width)
            self._apply_table_layout()
            if self._wrap_text:
                self._clear_row_height_cache()
                self._schedule_row_resize()
            return
        if logical_index == 3:
            self._status_column_width = max(60, _new)
            self._prefs_extras["TABLE_STATUS_WIDTH"] = str(self._status_column_width)
            self._apply_table_layout()
            if self._wrap_text:
                self._clear_row_height_cache()
                self._schedule_row_resize()
            return
        if logical_index not in (1, 2):
            return
        header = self.table.horizontalHeader()
        viewport_width = max(0, self.table.viewport().width())
        key_width = header.sectionSize(0)
        status_width = header.sectionSize(3)
        available = max(0, viewport_width - key_width - status_width)
        if available <= 0:
            return
        min_content = 60
        if logical_index == 1:
            source_width = max(min_content, min(available - min_content, _new))
            translation_width = max(min_content, available - source_width)
        else:
            translation_width = max(min_content, min(available - min_content, _new))
            source_width = max(min_content, available - translation_width)
        self._table_layout_guard = True
        try:
            header.resizeSection(1, source_width)
            header.resizeSection(2, translation_width)
        finally:
            self._table_layout_guard = False
        total = source_width + translation_width
        if total > 0:
            self._source_translation_ratio = source_width / total
            self._user_resized_columns = True
            self._prefs_extras["TABLE_SRC_RATIO"] = (
                f"{self._source_translation_ratio:.6f}"
            )
        if self._wrap_text:
            self._clear_row_height_cache()
            self._schedule_row_resize()

    def _save_current(self) -> bool:
        """Patch file on disk if there are unsaved value edits."""
        if not (self._current_pf and self._current_model):
            return True
        if not self._ensure_conflicts_resolved(self._current_pf.path):
            return False
        if not self._current_model.changed_keys():
            return True

        changed = self._current_model.changed_values()
        try:
            if changed:
                save(self._current_pf, changed, encoding=self._current_encoding)

            # persist cache for this file only (statuses + draft values)
            _write_status_cache(
                self._root,
                self._current_pf.path,
                self._current_pf.entries,
                changed_keys=set(),
                last_opened=int(time.time()),
            )

            self._current_model.reset_baseline()
            self.fs_model.set_dirty(self._current_pf.path, False)
            self._set_saved_status()
        except Exception as exc:
            QMessageBox.critical(self, "Save failed", str(exc))
            return False
        return True

    def _request_write_original(self) -> None:
        self._write_cache_current()
        files = self._draft_files()
        if not files:
            QMessageBox.information(
                self, "Nothing to write", "No draft changes to write."
            )
            return
        rel_files = [str(p.relative_to(self._root)) for p in files]
        dialog = SaveFilesDialog(rel_files, self)
        dialog.exec()
        decision = dialog.choice()
        if decision == "cancel":
            return
        if decision == "write":
            self._save_all_files(files)
        else:
            self._write_cache_current()

    def _draft_files(self) -> list[Path]:
        cache_root = self._root / self._app_config.cache_dir
        if not cache_root.exists():
            return []
        files: list[Path] = []
        for cache_path in cache_root.rglob(f"*{self._app_config.cache_ext}"):
            try:
                rel = cache_path.relative_to(cache_root)
            except ValueError:
                continue
            original = (self._root / rel).with_suffix(self._app_config.translation_ext)
            if not original.exists():
                continue
            if original not in self._opened_files:
                continue
            if _read_has_drafts_from_path(cache_path):
                files.append(original)
        return sorted(set(files))

    def _all_draft_files(self, locales: Iterable[str] | None = None) -> list[Path]:
        cache_root = self._root / self._app_config.cache_dir
        if not cache_root.exists():
            return []
        locale_list = [loc for loc in locales or [] if loc]
        cache_dirs = (
            [cache_root / loc for loc in locale_list] if locale_list else [cache_root]
        )
        files: list[Path] = []
        for cache_dir in cache_dirs:
            if not cache_dir.exists():
                continue
            for cache_path in cache_dir.rglob(f"*{self._app_config.cache_ext}"):
                try:
                    rel = cache_path.relative_to(cache_root)
                except ValueError:
                    continue
                original = (self._root / rel).with_suffix(
                    self._app_config.translation_ext
                )
                if not original.exists():
                    continue
                if _read_has_drafts_from_path(cache_path):
                    files.append(original)
        return sorted(set(files))

    def _mark_cached_dirty(self) -> None:
        perf_trace = PERF_TRACE
        perf_start = perf_trace.start("cache_scan")
        paths = self._all_draft_files(self._selected_locales)
        for path in paths:
            self.fs_model.set_dirty(path, True)
        perf_trace.stop("cache_scan", perf_start, items=len(paths), unit="files")

    def _schedule_post_locale_tasks(self) -> None:
        if self._post_locale_timer.isActive():
            self._post_locale_timer.stop()
        self._post_locale_timer.start()

    def _run_post_locale_tasks(self) -> None:
        perf_trace = PERF_TRACE
        perf_start = perf_trace.start("startup")
        try:
            self._mark_cached_dirty()
            self._auto_open_last_file()
        finally:
            perf_trace.stop("startup", perf_start, items=1, unit="tasks")

    def _hash_for_cache(
        self, key: str | Entry, cache_map: dict[int, CacheEntry]
    ) -> int:
        if isinstance(key, Entry):
            digest = key.key_hash
            key_text = key.key
        else:
            digest = None
            key_text = key
        if digest is None:
            digest = int(xxhash.xxh64(key_text.encode("utf-8")).intdigest())
        bits = getattr(cache_map, "hash_bits", 64)
        if bits == 16:
            return digest & 0xFFFF
        return digest & 0xFFFFFFFFFFFFFFFF

    def _auto_open_last_file(self) -> None:
        perf_trace = PERF_TRACE
        perf_start = perf_trace.start("auto_open")
        scanned = 0
        try:
            cache_root = self._root / self._app_config.cache_dir
            if not cache_root.exists():
                return
            locale_dirs = [cache_root / loc for loc in self._selected_locales if loc]
            if not locale_dirs:
                return
            best_ts = 0
            best_path: Path | None = None
            for cache_dir in locale_dirs:
                if not cache_dir.exists():
                    continue
                for cache_path in cache_dir.rglob(f"*{self._app_config.cache_ext}"):
                    scanned += 1
                    ts = _read_last_opened_from_path(cache_path)
                    if ts <= 0:
                        continue
                    try:
                        rel = cache_path.relative_to(cache_root)
                    except ValueError:
                        continue
                    original = (self._root / rel).with_suffix(
                        self._app_config.translation_ext
                    )
                    if not original.exists():
                        continue
                    locale = self._locale_for_path(original)
                    if locale not in self._selected_locales:
                        continue
                    if ts > best_ts:
                        best_ts = ts
                        best_path = original
            if not best_path:
                return
            index = self.fs_model.index_for_path(best_path)
            if index.isValid():
                self._file_chosen(index)
        finally:
            perf_trace.stop("auto_open", perf_start, items=scanned, unit="files")

    def _schedule_cache_migration(self) -> None:
        legacy_paths = _legacy_cache_paths(self._root)
        if not legacy_paths:
            return
        if len(legacy_paths) <= self._migration_batch_size:
            try:
                migrated = _migrate_status_caches(self._root, self._locales)
            except Exception as exc:
                QMessageBox.warning(self, "Cache migration failed", str(exc))
                return
            if migrated:
                self._migration_count += migrated
            return
        self._pending_cache_migrations = list(legacy_paths)
        self._migration_count = 0
        if self._migration_timer is None:
            self._migration_timer = QTimer(self)
            self._migration_timer.timeout.connect(self._run_cache_migration_batch)
        if not self._migration_timer.isActive():
            self._migration_timer.start(0)

    def _run_cache_migration_batch(self) -> None:
        if not self._pending_cache_migrations:
            if self._migration_timer is not None:
                self._migration_timer.stop()
            if self._migration_count:
                self.statusBar().showMessage(
                    f"Migrated {self._migration_count} cache file(s).", 5000
                )
            return
        batch = self._pending_cache_migrations[: self._migration_batch_size]
        del self._pending_cache_migrations[: self._migration_batch_size]
        try:
            migrated = _migrate_status_cache_paths(self._root, self._locales, batch)
        except Exception as exc:
            if self._migration_timer is not None:
                self._migration_timer.stop()
            QMessageBox.warning(self, "Cache migration failed", str(exc))
            return
        self._migration_count += migrated

    def _warn_orphan_caches(self) -> None:
        cache_root = self._root / self._app_config.cache_dir
        if not cache_root.exists():
            return
        for locale in self._selected_locales:
            if locale in self._orphan_cache_warned_locales:
                continue
            locale_cache = cache_root / locale
            if not locale_cache.exists():
                continue
            missing: list[Path] = []
            for cache_path in locale_cache.rglob(f"*{self._app_config.cache_ext}"):
                try:
                    rel = cache_path.relative_to(cache_root)
                except ValueError:
                    continue
                original = (self._root / rel).with_suffix(
                    self._app_config.translation_ext
                )
                if not original.exists():
                    missing.append(cache_path)
            if not missing:
                continue
            self._orphan_cache_warned_locales.add(locale)
            rels = [str(p.relative_to(cache_root)) for p in missing]
            preview = "\n".join(rels[:20])
            if len(rels) > 20:
                preview = f"{preview}\n... ({len(rels) - 20} more)"
            msg = QMessageBox(self)
            msg.setIcon(QMessageBox.Warning)
            msg.setWindowTitle("Orphan cache files")
            msg.setText(f"Locale {locale} has cache files without source files.")
            msg.setInformativeText(
                "Purge deletes those cache files. Dismiss keeps them."
            )
            msg.setDetailedText(preview)
            purge = msg.addButton("Purge", QMessageBox.AcceptRole)
            msg.addButton("Dismiss", QMessageBox.RejectRole)
            msg.exec()
            if msg.clickedButton() is purge:
                for path in missing:
                    try:
                        path.unlink()
                    except OSError:
                        continue

    def _save_all_files(self, files: list[Path]) -> None:
        if not files:
            return
        remaining = list(files)
        if self._current_pf and self._current_pf.path in remaining:
            if not self._save_current():
                return
            remaining.remove(self._current_pf.path)
        failures: list[Path] = []
        for path in remaining:
            if not self._save_file_from_cache(path):
                failures.append(path)
        if failures:
            rel = "\n".join(str(p.relative_to(self._root)) for p in failures)
            QMessageBox.warning(
                self,
                "Save incomplete",
                f"Some files could not be written:\n{rel}",
            )
        else:
            self._set_saved_status()

    def _save_file_from_cache(self, path: Path) -> bool:
        if not self._ensure_conflicts_resolved(path):
            return False
        cached = _read_status_cache(self._root, path)
        if not any(entry.value is not None for entry in cached.values()):
            return True
        locale = self._locale_for_path(path)
        encoding = self._locales.get(
            locale, LocaleMeta("", Path(), "", "utf-8")
        ).charset
        try:
            pf = parse(path, encoding=encoding)
        except Exception as exc:
            self._report_parse_error(path, exc)
            return False
        changed: dict[str, str] = {}
        new_entries = []
        for e in pf.entries:
            h = self._hash_for_cache(e, cached)
            rec = cached.get(h)
            if rec is None:
                new_entries.append(e)
                continue
            if rec.status != e.status:
                e = type(e)(
                    e.key,
                    e.value,
                    rec.status,
                    e.span,
                    e.segments,
                    e.gaps,
                    e.raw,
                    getattr(e, "key_hash", None),
                )
            if rec.value is not None:
                changed[e.key] = rec.value
            new_entries.append(e)
        pf.entries = new_entries
        if changed:
            save(pf, changed, encoding=encoding)
        _write_status_cache(self._root, path, pf.entries, changed_keys=set())
        self.fs_model.set_dirty(path, False)
        return True

    def _write_cache_current(self) -> bool:
        if not (self._current_pf and self._current_model):
            return True
        if self._detail_panel.isVisible():
            self._commit_detail_translation()
        changed_rows = self._current_model.changed_rows_with_source()
        try:
            original_values = self._current_model.baseline_values()
            _write_status_cache(
                self._root,
                self._current_pf.path,
                self._current_pf.entries,
                changed_keys=self._current_model.changed_keys(),
                last_opened=int(time.time()),
                original_values=original_values,
            )
        except Exception as exc:
            QMessageBox.critical(self, "Cache write failed", str(exc))
            return False
        if self._current_model.changed_keys():
            self.fs_model.set_dirty(self._current_pf.path, True)
        else:
            self.fs_model.set_dirty(self._current_pf.path, False)
        if changed_rows:
            self._queue_tm_updates(self._current_pf.path, changed_rows)
        return True

    def _queue_tm_updates(
        self, path: Path, rows: Iterable[tuple[str, str, str]]
    ) -> None:
        if not self._tm_store:
            return
        self._tm_cache.clear()
        file_key = str(path)
        bucket = self._tm_pending.setdefault(file_key, {})
        for key, source_text, value_text in rows:
            bucket[key] = (key, source_text, value_text)
        if self._tm_flush_timer.isActive():
            self._tm_flush_timer.stop()
        self._tm_flush_timer.start()

    def _flush_tm_updates(self, *, paths: Iterable[Path] | None = None) -> None:
        if not self._tm_store or not self._tm_pending:
            return
        if paths is None:
            pending_items = list(self._tm_pending.items())
        else:
            wanted = {str(path) for path in paths}
            pending_items = [
                (path_key, rows)
                for path_key, rows in self._tm_pending.items()
                if path_key in wanted
            ]
        for path_key, rows in pending_items:
            if not rows:
                continue
            locale = self._locale_for_path(Path(path_key))
            if not locale:
                continue
            try:
                self._tm_store.upsert_project_entries(
                    rows.values(),
                    source_locale=self._tm_source_locale,
                    target_locale=locale,
                    file_path=path_key,
                )
            except Exception as exc:
                QMessageBox.warning(self, "TM update failed", str(exc))
                continue
            self._tm_pending.pop(path_key, None)

    def _on_model_changed(self, *_args) -> None:
        if not (self._current_pf and self._current_model):
            return
        self._write_cache_current()

    def _focus_search(self) -> None:
        self.search_edit.setFocus()
        self.search_edit.selectAll()

    def _trigger_search(self) -> None:
        if self._search_timer.isActive():
            self._search_timer.stop()
        self._search_next()

    def _open_regex_help(self) -> None:
        QDesktopServices.openUrl(QUrl("https://docs.python.org/3/library/re.html"))

    def _schedule_search(self, *_args) -> None:
        self._on_search_controls_changed()

    def _on_search_controls_changed(self, *_args) -> None:
        # Search runs only on explicit Enter/Next/Prev, not on typing.
        self._update_replace_enabled()
        self._search_progress_text = ""
        self._update_status_bar()
        if self._search_timer.isActive():
            self._search_timer.stop()

    def _toggle_replace(self, checked: bool) -> None:
        self._replace_visible = bool(checked)
        self.replace_toolbar.setVisible(self._replace_visible)
        if self._replace_visible:
            self._align_replace_bar()
            QTimer.singleShot(0, self._align_replace_bar)
        self._update_replace_toggle_icon(self._replace_visible)
        self._update_replace_enabled()
        self._update_status_bar()

    def _update_replace_toggle_icon(self, visible: bool) -> None:
        if visible:
            self.replace_toggle.setIcon(self._replace_icon_active)
            self.replace_toggle.setToolTip("Hide replace")
        else:
            self.replace_toggle.setIcon(self._replace_icon)
            self.replace_toggle.setToolTip("Show replace")

    def _align_replace_bar(self) -> None:
        if not self.replace_toolbar.isVisible():
            return
        search_pos = self.search_edit.mapToGlobal(QPoint(0, 0)).x()
        replace_pos = self.replace_edit.mapToGlobal(QPoint(0, 0)).x()
        delta = search_pos - replace_pos
        new_width = max(0, self.replace_spacer.width() + delta)
        self.replace_spacer.setFixedWidth(new_width)

    def _update_replace_enabled(self, *_args) -> None:
        mode = int(self.search_mode.currentData())
        has_query = bool(self.search_edit.text().strip())
        replace_allowed = bool(self._current_model and mode == _SearchField.TRANSLATION)
        if not replace_allowed and self.replace_toggle.isChecked():
            self.replace_toggle.setChecked(False)
        self.replace_toggle.setEnabled(replace_allowed)
        enabled = bool(replace_allowed and has_query)
        for widget in (self.replace_edit, self.replace_btn, self.replace_all_btn):
            widget.setEnabled(enabled)

    def _prepare_replace_pattern(
        self,
    ) -> tuple[re.Pattern[str] | None, str, bool, bool, bool]:
        query = self.search_edit.text()
        if not query:
            return None, "", False, False, False
        use_regex = self.regex_check.isChecked()
        flags = re.IGNORECASE | re.MULTILINE
        try:
            if use_regex:
                pattern = re.compile(query, flags)
            else:
                pattern = re.compile(re.escape(query), flags)
        except re.error:
            QMessageBox.warning(self, "Invalid regex", "Regex pattern is invalid.")
            return None, "", False, False, False
        replacement = self.replace_edit.text()
        matches_empty = bool(pattern.match(""))
        has_group_ref = bool(
            use_regex and re.search(r"\$(\d+)|\\g<\\d+>|\\[1-9]", replacement)
        )
        return pattern, replacement, use_regex, matches_empty, has_group_ref

    def _files_for_scope(self, scope: str) -> list[Path]:
        if not self._current_pf:
            return []
        if scope == "FILE":
            return [self._current_pf.path]
        if scope == "LOCALE":
            locale = self._locale_for_path(self._current_pf.path)
            if not locale:
                return []
            return list(self._files_for_locale(locale))
        files: list[Path] = []
        for locale in self._selected_locales:
            files.extend(self._files_for_locale(locale))
        return files

    def _files_for_locale(self, locale: str) -> list[Path]:
        cached = self._files_by_locale.get(locale)
        if cached is not None:
            return cached
        meta = self._locales.get(locale)
        if not meta:
            return []
        files = list_translatable_files(meta.path)
        self._files_by_locale[locale] = files
        return files

    def _replace_current(self) -> None:
        if not self._current_model:
            return
        pattern, replacement, use_regex, matches_empty, has_group_ref = (
            self._prepare_replace_pattern()
        )
        if pattern is None:
            return
        current = self.table.currentIndex()
        if not current.isValid():
            return
        row = current.row()
        idx = self._current_model.index(row, 2)
        text = idx.data(Qt.DisplayRole)
        text = "" if text is None else str(text)
        if not pattern.search(text):
            return
        if matches_empty and not has_group_ref:
            new_text = replacement
        else:
            try:
                if use_regex:
                    template = re.sub(r"\$(\d+)", r"\\g<\1>", replacement)
                    count = 1 if matches_empty else 1
                    new_text = pattern.sub(
                        lambda m: m.expand(template), text, count=count
                    )
                else:
                    new_text = pattern.sub(lambda _m: replacement, text, count=1)
            except re.error as exc:
                QMessageBox.warning(self, "Replace failed", str(exc))
                return
        if new_text != text:
            self._current_model.setData(idx, new_text, Qt.EditRole)
            self._schedule_search()

    def _replace_all_text(
        self,
        text: str,
        pattern: re.Pattern[str],
        replacement: str,
        use_regex: bool,
        matches_empty: bool,
        has_group_ref: bool,
    ) -> tuple[bool, str] | None:
        if not text:
            return False, text
        if matches_empty and not has_group_ref:
            new_text = replacement
        else:
            if not pattern.search(text):
                return False, text
            try:
                if use_regex:
                    template = re.sub(r"\$(\d+)", r"\\g<\1>", replacement)
                    count = 1 if matches_empty else 0
                    new_text = pattern.sub(
                        lambda m, template=template: m.expand(template),
                        text,
                        count=count,
                    )
                else:
                    new_text = pattern.sub(lambda _m: replacement, text)
            except re.error as exc:
                QMessageBox.warning(self, "Replace failed", str(exc))
                return None
        return new_text != text, new_text

    def _replace_all_count_in_model(
        self,
        pattern: re.Pattern[str],
        replacement: str,
        use_regex: bool,
        matches_empty: bool,
        has_group_ref: bool,
    ) -> int | None:
        if not self._current_model:
            return 0
        count = 0
        for row in range(self._current_model.rowCount()):
            idx = self._current_model.index(row, 2)
            text = idx.data(Qt.DisplayRole)
            text = "" if text is None else str(text)
            result = self._replace_all_text(
                text, pattern, replacement, use_regex, matches_empty, has_group_ref
            )
            if result is None:
                return None
            changed, _new_text = result
            if changed:
                count += 1
        return count

    def _replace_all_count_in_file(
        self,
        path: Path,
        pattern: re.Pattern[str],
        replacement: str,
        use_regex: bool,
        matches_empty: bool,
        has_group_ref: bool,
    ) -> int | None:
        locale = self._locale_for_path(path)
        encoding = self._locales.get(
            locale, LocaleMeta("", Path(), "", "utf-8")
        ).charset
        try:
            pf = parse(path, encoding=encoding)
        except Exception as exc:
            self._report_parse_error(path, exc)
            return None
        cache_map = _read_status_cache(self._root, path)
        count = 0
        for entry in pf.entries:
            key_hash = self._hash_for_cache(entry, cache_map)
            cache = cache_map.get(key_hash)
            value = cache.value if cache and cache.value is not None else entry.value
            text = "" if value is None else str(value)
            result = self._replace_all_text(
                text, pattern, replacement, use_regex, matches_empty, has_group_ref
            )
            if result is None:
                return None
            changed, _new_text = result
            if changed:
                count += 1
        return count

    def _replace_all(self) -> None:
        if not self._current_model:
            return
        pattern, replacement, use_regex, matches_empty, has_group_ref = (
            self._prepare_replace_pattern()
        )
        if pattern is None:
            return
        scope = self._replace_scope
        files = self._files_for_scope(scope)
        if not files:
            return
        if scope != "FILE" and len(files) > 1:
            if scope == "LOCALE":
                locale = (
                    self._locale_for_path(self._current_pf.path)
                    if self._current_pf
                    else None
                )
                scope_label = f"Locale {locale}" if locale else "Locale"
            else:
                scope_label = f"Pool ({len(self._selected_locales)})"
            counts: list[tuple[str, int]] = []
            total = 0
            current_path = self._current_pf.path if self._current_pf else None
            for path in files:
                if current_path and path == current_path:
                    file_count = self._replace_all_count_in_model(
                        pattern, replacement, use_regex, matches_empty, has_group_ref
                    )
                else:
                    file_count = self._replace_all_count_in_file(
                        path,
                        pattern,
                        replacement,
                        use_regex,
                        matches_empty,
                        has_group_ref,
                    )
                if file_count is None:
                    return
                total += file_count
                if file_count:
                    try:
                        rel = str(path.relative_to(self._root))
                    except ValueError:
                        rel = str(path)
                    counts.append((rel, file_count))
            if total == 0:
                return
            dialog = ReplaceFilesDialog(counts, scope_label, self)
            dialog.exec()
            if not dialog.confirmed():
                return
        if (
            self._current_pf
            and self._current_pf.path in files
            and not self._replace_all_in_model(
                pattern, replacement, use_regex, matches_empty, has_group_ref
            )
        ):
            return
        for path in files:
            if self._current_pf and path == self._current_pf.path:
                continue
            if not self._replace_all_in_file(
                path, pattern, replacement, use_regex, matches_empty, has_group_ref
            ):
                return
        self._schedule_search()

    def _replace_all_in_model(
        self,
        pattern: re.Pattern[str],
        replacement: str,
        use_regex: bool,
        matches_empty: bool,
        has_group_ref: bool,
    ) -> bool:
        if not self._current_model:
            return True
        for row in range(self._current_model.rowCount()):
            idx = self._current_model.index(row, 2)
            text = idx.data(Qt.DisplayRole)
            text = "" if text is None else str(text)
            result = self._replace_all_text(
                text, pattern, replacement, use_regex, matches_empty, has_group_ref
            )
            if result is None:
                return False
            changed, new_text = result
            if changed:
                self._current_model.setData(idx, new_text, Qt.EditRole)
        return True

    def _replace_all_in_file(
        self,
        path: Path,
        pattern: re.Pattern[str],
        replacement: str,
        use_regex: bool,
        matches_empty: bool,
        has_group_ref: bool,
    ) -> bool:
        locale = self._locale_for_path(path)
        encoding = self._locales.get(
            locale, LocaleMeta("", Path(), "", "utf-8")
        ).charset
        try:
            pf = parse(path, encoding=encoding)
        except Exception as exc:
            self._report_parse_error(path, exc)
            return False
        cache_map = _read_status_cache(self._root, path)
        changed_keys: set[str] = set()
        original_values: dict[str, str] = {}
        new_entries = []
        for entry in pf.entries:
            key_hash = self._hash_for_cache(entry, cache_map)
            cache = cache_map.get(key_hash)
            value = cache.value if cache and cache.value is not None else entry.value
            status = cache.status if cache else entry.status
            text = "" if value is None else str(value)
            result = self._replace_all_text(
                text, pattern, replacement, use_regex, matches_empty, has_group_ref
            )
            if result is None:
                return False
            _changed, new_value = result
            if new_value != text:
                status = Status.TRANSLATED
                changed_keys.add(entry.key)
                original_values[entry.key] = text
            if new_value != entry.value or status != entry.status:
                entry = type(entry)(
                    entry.key,
                    new_value,
                    status,
                    entry.span,
                    entry.segments,
                    entry.gaps,
                    entry.raw,
                    getattr(entry, "key_hash", None),
                )
            new_entries.append(entry)
        _write_status_cache(
            self._root,
            path,
            new_entries,
            changed_keys=changed_keys,
            original_values=original_values,
            force_original=set(original_values),
        )
        if changed_keys:
            self.fs_model.set_dirty(path, True)
        return True

    def _report_parse_error(self, path: Path, exc: Exception) -> None:
        message = f"{path}\n\n{exc}"
        QMessageBox.warning(self, "Parse error", message)
        print(f"[Parse error] {path}", file=sys.stderr)
        traceback.print_exception(type(exc), exc, exc.__traceback__, file=sys.stderr)

    # ── conflict handling -------------------------------------------------
    def _register_conflicts(
        self,
        path: Path,
        originals: dict[str, str],
        sources: dict[str, str],
    ) -> None:
        self._conflict_files[path] = originals
        self._conflict_sources[path] = sources
        if path not in self._conflict_notified:
            self._conflict_notified.add(path)
            QTimer.singleShot(0, lambda p=path: self._prompt_conflicts(p))

    def _clear_conflicts(self, path: Path) -> None:
        self._conflict_files.pop(path, None)
        self._conflict_sources.pop(path, None)
        self._conflict_notified.discard(path)

    def _has_conflicts(self, path: Path) -> bool:
        return bool(self._conflict_files.get(path))

    def _prompt_conflicts(self, path: Path, *, for_save: bool = False) -> bool:
        if not self._has_conflicts(path):
            return True
        if not self._current_pf or self._current_pf.path != path:
            return not for_save
        rel = str(path.relative_to(self._root))
        dialog = ConflictChoiceDialog(rel, len(self._conflict_files[path]), self)
        dialog.exec()
        choice = dialog.choice()
        if choice is None:
            return False
        if choice == "drop_cache":
            return self._resolve_conflicts_drop_cache(path)
        if choice == "drop_original":
            return self._resolve_conflicts_drop_original(path)
        if choice == "merge":
            return self._resolve_conflicts_merge(path)
        return False

    def _ensure_conflicts_resolved(self, path: Path) -> bool:
        if not self._has_conflicts(path):
            return True
        return self._prompt_conflicts(path, for_save=True)

    def _reload_file(self, path: Path) -> None:
        index = self.fs_model.index_for_path(path)
        if not index.isValid():
            return
        self._skip_conflict_check = True
        self._skip_cache_write = True
        self._file_chosen(index)

    def _resolve_conflicts_drop_cache(self, path: Path) -> bool:
        if not (self._current_pf and self._current_model):
            return False
        if self._current_pf.path != path:
            return False
        conflict_keys = set(self._conflict_files.get(path, {}))
        changed_keys = set(self._current_model.changed_keys()) - conflict_keys
        original_values = self._current_model.baseline_values()
        _write_status_cache(
            self._root,
            path,
            self._current_pf.entries,
            changed_keys=changed_keys,
            original_values=original_values,
        )
        if not changed_keys:
            self.fs_model.set_dirty(path, False)
        self._clear_conflicts(path)
        self._reload_file(path)
        return True

    def _resolve_conflicts_drop_original(self, path: Path) -> bool:
        if not (self._current_pf and self._current_model):
            return False
        if self._current_pf.path != path:
            return False
        conflict_originals = self._conflict_files.get(path, {})
        changed_keys = set(self._current_model.changed_keys())
        original_values = self._current_model.baseline_values()
        original_values.update(conflict_originals)
        _write_status_cache(
            self._root,
            path,
            self._current_pf.entries,
            changed_keys=changed_keys,
            original_values=original_values,
            force_original=set(conflict_originals),
        )
        self._clear_conflicts(path)
        self._reload_file(path)
        return True

    def _resolve_conflicts_merge(self, path: Path) -> bool:
        if not (self._current_pf and self._current_model):
            return False
        if self._current_pf.path != path:
            return False
        conflict_originals = self._conflict_files.get(path, {})
        if not conflict_originals:
            return True
        sources = self._conflict_sources.get(path, {})
        cache_values = {
            entry.key: entry.value
            for entry in self._current_pf.entries
            if entry.key in conflict_originals
        }
        rows = [
            (
                key,
                sources.get(key, ""),
                conflict_originals.get(key, ""),
                cache_values.get(key, ""),
            )
            for key in sorted(conflict_originals)
        ]
        resolutions = self._run_merge_ui(path, rows)
        if not resolutions:
            return False
        changed_keys = set(self._current_model.changed_keys())
        original_values = self._current_model.baseline_values()
        keep_conflict: set[str] = set()
        updates: dict[str, str] = {}
        status_updates: dict[str, Status] = {}
        for key, (chosen_value, _choice) in resolutions.items():
            original_value = conflict_originals.get(key, "")
            if chosen_value == original_value:
                changed_keys.discard(key)
            else:
                changed_keys.add(key)
                original_values[key] = original_value
                keep_conflict.add(key)
            if chosen_value != cache_values.get(key, ""):
                updates[key] = chosen_value
            if _choice == "original":
                status_updates[key] = Status.FOR_REVIEW
        if updates or status_updates:
            for idx, entry in enumerate(self._current_pf.entries):
                if entry.key not in updates and entry.key not in status_updates:
                    continue
                new_value = updates.get(entry.key, entry.value)
                new_status = status_updates.get(entry.key, entry.status)
                if new_value == entry.value and new_status == entry.status:
                    continue
                self._current_pf.entries[idx] = type(entry)(
                    entry.key,
                    new_value,
                    new_status,
                    entry.span,
                    entry.segments,
                    entry.gaps,
                    entry.raw,
                    getattr(entry, "key_hash", None),
                )
        _write_status_cache(
            self._root,
            path,
            self._current_pf.entries,
            changed_keys=changed_keys,
            original_values=original_values,
            force_original=keep_conflict,
        )
        if not changed_keys:
            self.fs_model.set_dirty(path, False)
        self._clear_conflicts(path)
        self._reload_file(path)
        return True

    def _run_merge_ui(
        self, path: Path, rows: list[tuple[str, str, str, str]]
    ) -> dict[str, tuple[str, str]] | None:
        if self._merge_active:
            return None
        self._merge_result = None
        self._build_merge_view(path, rows)
        self._set_merge_active(True)
        loop = QEventLoop()
        self._merge_loop = loop
        loop.exec()
        self._merge_loop = None
        self._set_merge_active(False)
        return self._merge_result

    def _build_merge_view(
        self, path: Path, rows: list[tuple[str, str, str, str]]
    ) -> None:
        if self._merge_container is not None:
            self._right_stack.removeWidget(self._merge_container)
            self._merge_container.deleteLater()
        self._merge_rows = []
        self._merge_container = QWidget(self)
        layout = QVBoxLayout(self._merge_container)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)
        rel = str(path.relative_to(self._root))
        layout.addWidget(QLabel(f"Resolve conflicts for {rel}", self._merge_container))

        table = QTableWidget(self._merge_container)
        table.setColumnCount(6)
        table.setHorizontalHeaderLabels(
            ["Key", "Source", "Original", "Cache", "Original ✓", "Cache ✓"]
        )
        table.setRowCount(0)
        table.setWordWrap(True)
        table.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed
        )
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)

        for key, source, original, cache in rows:
            row = table.rowCount()
            table.insertRow(row)

            key_item = QTableWidgetItem(key)
            key_item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
            table.setItem(row, 0, key_item)

            source_item = QTableWidgetItem(source)
            source_item.setFlags(
                Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled
            )
            table.setItem(row, 1, source_item)

            original_item = QTableWidgetItem(original)
            original_item.setFlags(
                Qt.ItemFlag.ItemIsSelectable
                | Qt.ItemFlag.ItemIsEnabled
                | Qt.ItemFlag.ItemIsEditable
            )
            table.setItem(row, 2, original_item)

            cache_item = QTableWidgetItem(cache)
            cache_item.setFlags(
                Qt.ItemFlag.ItemIsSelectable
                | Qt.ItemFlag.ItemIsEnabled
                | Qt.ItemFlag.ItemIsEditable
            )
            table.setItem(row, 3, cache_item)

            group = QButtonGroup(self._merge_container)
            group.setExclusive(True)
            btn_original = QRadioButton(self._merge_container)
            btn_cache = QRadioButton(self._merge_container)
            group.addButton(btn_original)
            group.addButton(btn_cache)
            table.setCellWidget(row, 4, btn_original)
            table.setCellWidget(row, 5, btn_cache)
            btn_original.toggled.connect(self._update_merge_apply_enabled)
            btn_cache.toggled.connect(self._update_merge_apply_enabled)

            self._merge_rows.append(
                (key, original_item, cache_item, btn_original, btn_cache)
            )

        table.resizeColumnsToContents()
        table.horizontalHeader().setStretchLastSection(False)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        table.setMinimumHeight(320)
        layout.addWidget(table)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        apply_btn = QPushButton("Apply", self._merge_container)
        apply_btn.setEnabled(False)
        apply_btn.clicked.connect(self._apply_merge_resolutions)
        btn_row.addWidget(apply_btn)
        layout.addLayout(btn_row)

        self._merge_apply_btn = apply_btn
        self._right_stack.addWidget(self._merge_container)

    def _update_merge_apply_enabled(self) -> None:
        if not self._merge_rows or self._merge_apply_btn is None:
            return
        ready = all(
            btn_original.isChecked() or btn_cache.isChecked()
            for _key, _orig_item, _cache_item, btn_original, btn_cache in self._merge_rows
        )
        self._merge_apply_btn.setEnabled(bool(ready))

    def _apply_merge_resolutions(self) -> None:
        for _key, _orig_item, _cache_item, btn_original, btn_cache in self._merge_rows:
            if not (btn_original.isChecked() or btn_cache.isChecked()):
                QMessageBox.warning(
                    self,
                    "Incomplete selection",
                    "Choose Original or Cache for every row.",
                )
                return
        out: dict[str, tuple[str, str]] = {}
        for key, orig_item, cache_item, btn_original, btn_cache in self._merge_rows:
            if btn_original.isChecked():
                out[key] = (orig_item.text(), "original")
            elif btn_cache.isChecked():
                out[key] = (cache_item.text(), "cache")
        self._merge_result = out
        if self._merge_loop is not None and self._merge_loop.isRunning():
            self._merge_loop.quit()

    def _set_merge_active(self, active: bool) -> None:
        self._merge_active = active
        self.tree.setEnabled(not active)
        self.table.setEnabled(not active)
        self.toolbar.setEnabled(not active)
        self.replace_toolbar.setEnabled(not active)
        self.menuBar().setEnabled(not active)
        self._detail_panel.setVisible(not active)
        if active and self._merge_container is not None:
            self._right_stack.setCurrentWidget(self._merge_container)
        else:
            self._right_stack.setCurrentWidget(self._table_container)

    def _rows_from_model(
        self, *, include_source: bool = True, include_value: bool = True
    ) -> Iterable[_SearchRow]:
        if not (self._current_model and self._current_pf):
            return ()
        return self._current_model.iter_search_rows(
            include_source=include_source, include_value=include_value
        )

    def _rows_from_file(
        self,
        path: Path,
        locale: str,
        *,
        include_source: bool = True,
        include_value: bool = True,
    ) -> tuple[Iterable[_SearchRow], int]:
        meta = self._locales.get(locale)
        encoding = meta.charset if meta else "utf-8"
        try:
            if self._should_parse_lazy(path):
                pf = parse_lazy(path, encoding=encoding)
            else:
                pf = parse(path, encoding=encoding)
        except Exception:
            return (), 0
        cache_map = _read_status_cache(self._root, path) if include_value else {}
        use_cache = include_value and bool(cache_map)
        source_lookup = (
            self._load_en_source(path, locale, target_entries=pf.entries)
            if include_source
            else _SourceLookup(by_key={})
        )
        source_by_row = source_lookup.by_row
        entry_count = len(pf.entries)

        def _iter_rows() -> Iterable[_SearchRow]:
            for idx, entry in enumerate(pf.entries):
                key = entry.key
                value = ""
                if include_value:
                    if use_cache:
                        key_hash = self._hash_for_cache(entry, cache_map)
                        rec = cache_map.get(key_hash)
                        value = (
                            rec.value if rec and rec.value is not None else entry.value
                        )
                    else:
                        value = entry.value
                yield _SearchRow(
                    file=path,
                    row=idx,
                    key=key,
                    source=(
                        source_by_row[idx]
                        if source_by_row is not None and idx < len(source_by_row)
                        else source_lookup.get(key, "")
                    ),
                    value="" if value is None else str(value),
                )

        if entry_count <= self._search_cache_row_limit:
            return list(_iter_rows()), entry_count
        return _iter_rows(), entry_count

    def _cached_rows_from_file(
        self,
        path: Path,
        locale: str,
        *,
        include_source: bool,
        include_value: bool,
    ) -> Iterable[_SearchRow]:
        try:
            file_mtime = path.stat().st_mtime_ns
        except OSError:
            return []
        cache_mtime = 0
        source_mtime = 0
        if include_value:
            try:
                rel = path.relative_to(self._root)
            except ValueError:
                rel = None
            if rel is not None:
                cache_path = (
                    self._root / self._app_config.cache_dir / rel
                ).with_suffix(self._app_config.cache_ext)
                with contextlib.suppress(OSError):
                    cache_mtime = cache_path.stat().st_mtime_ns
        if include_source:
            en_path = self._en_path_for(path, locale)
            if en_path:
                with contextlib.suppress(OSError):
                    source_mtime = en_path.stat().st_mtime_ns
        stamp = (file_mtime, cache_mtime, source_mtime)
        key = (path, include_source, include_value)
        cached = self._search_rows_cache.get(key)
        if cached and cached[0] == stamp:
            self._search_rows_cache.move_to_end(key)
            return cached[1]
        rows, entry_count = self._rows_from_file(
            path,
            locale,
            include_source=include_source,
            include_value=include_value,
        )
        if isinstance(rows, list) and entry_count <= self._search_cache_row_limit:
            self._search_rows_cache[key] = (stamp, rows)
            self._search_rows_cache.move_to_end(key)
            if len(self._search_rows_cache) > self._search_cache_max:
                self._search_rows_cache.popitem(last=False)
        return rows

    def _search_files_for_scope(self) -> list[Path]:
        files = list(self._files_for_scope(self._search_scope))
        if self._current_pf and self._current_pf.path in files:
            current = self._current_pf.path
            files = [current, *[p for p in files if p != current]]
        return files

    def _search_anchor_row(self, direction: int) -> int:
        current = self.table.currentIndex()
        if current.isValid():
            return current.row()
        return -1 if direction > 0 else sys.maxsize

    def _find_match_in_rows(
        self,
        rows: Iterable[_SearchRow],
        query: str,
        field: _SearchField,
        use_regex: bool,
        *,
        start_row: int,
        direction: int,
    ) -> _SearchMatch | None:
        if direction >= 0:
            for match in _iter_search_matches(rows, query, field, use_regex):
                if match.row > start_row:
                    return match
            return None
        last_match: _SearchMatch | None = None
        for match in _iter_search_matches(rows, query, field, use_regex):
            if match.row >= start_row:
                break
            last_match = match
        return last_match

    def _find_match_in_file(
        self,
        path: Path,
        *,
        query: str,
        field: _SearchField,
        use_regex: bool,
        include_source: bool,
        include_value: bool,
        start_row: int,
        direction: int,
    ) -> _SearchMatch | None:
        locale = self._locale_for_path(path)
        if not locale:
            return None
        if self._current_pf and self._current_model and path == self._current_pf.path:
            rows = self._rows_from_model(
                include_source=include_source, include_value=include_value
            )
        else:
            rows = self._cached_rows_from_file(
                path,
                locale,
                include_source=include_source,
                include_value=include_value,
            )
        return self._find_match_in_rows(
            rows, query, field, use_regex, start_row=start_row, direction=direction
        )

    def _select_match(self, match: _SearchMatch) -> bool:
        if not match:
            return False
        if not self._current_pf or match.file != self._current_pf.path:
            index = self.fs_model.index_for_path(match.file)
            if not index.isValid():
                return False
            self._file_chosen(index)
            if self._current_pf and self._current_pf.path == match.file:
                self.tree.selectionModel().setCurrentIndex(
                    index,
                    QItemSelectionModel.ClearAndSelect | QItemSelectionModel.Rows,
                )
                self.tree.scrollTo(index, QAbstractItemView.PositionAtCenter)
        if not self._current_model or not self._current_pf:
            return False
        if match.file != self._current_pf.path:
            return False
        if match.row < 0 or match.row >= self._current_model.rowCount():
            return False
        column = self._search_column
        model_index = self._current_model.index(match.row, column)
        self.table.selectionModel().setCurrentIndex(
            model_index,
            QItemSelectionModel.ClearAndSelect | QItemSelectionModel.Rows,
        )
        self.table.scrollTo(model_index, QAbstractItemView.PositionAtCenter)
        return True

    def _search_from_anchor(
        self,
        *,
        direction: int,
        anchor_row: int | None = None,
        anchor_path: Path | None = None,
        wrap: bool = True,
    ) -> bool:
        query = self.search_edit.text().strip()
        self._search_progress_text = ""
        self._update_status_bar()
        if not query:
            return False
        column = int(self.search_mode.currentData())
        self._search_column = column
        use_regex = self.regex_check.isChecked()
        field_map = {
            0: _SearchField.KEY,
            1: _SearchField.SOURCE,
            2: _SearchField.TRANSLATION,
        }
        field = field_map.get(column, _SearchField.TRANSLATION)
        include_source = field is _SearchField.SOURCE
        include_value = field is _SearchField.TRANSLATION
        files = self._search_files_for_scope()
        if not files:
            return False
        if anchor_path is None:
            anchor_path = self._current_pf.path if self._current_pf else files[0]
        if anchor_row is None:
            anchor_row = self._search_anchor_row(direction)
        others = [p for p in files if p != anchor_path]
        if direction < 0:
            others = list(reversed(others))
        if anchor_path:
            match = self._find_match_in_file(
                anchor_path,
                query=query,
                field=field,
                use_regex=use_regex,
                include_source=include_source,
                include_value=include_value,
                start_row=anchor_row,
                direction=direction,
            )
            if match and self._select_match(match):
                return True
        fallback_row = -1 if direction > 0 else sys.maxsize
        for path in others:
            match = self._find_match_in_file(
                path,
                query=query,
                field=field,
                use_regex=use_regex,
                include_source=include_source,
                include_value=include_value,
                start_row=fallback_row,
                direction=direction,
            )
            if match and self._select_match(match):
                return True
        if not wrap or not anchor_path:
            return False
        if direction > 0 and anchor_row < 0:
            return False
        if direction < 0 and anchor_row >= sys.maxsize:
            return False
        match = self._find_match_in_file(
            anchor_path,
            query=query,
            field=field,
            use_regex=use_regex,
            include_source=include_source,
            include_value=include_value,
            start_row=fallback_row,
            direction=direction,
        )
        return bool(match and self._select_match(match))

    def _run_search(self) -> None:
        self._search_from_anchor(direction=1, anchor_row=-1)

    def _search_next(self) -> None:
        if self._search_timer.isActive():
            self._search_timer.stop()
        self._search_from_anchor(direction=1)

    def _search_prev(self) -> None:
        if self._search_timer.isActive():
            self._search_timer.stop()
        self._search_from_anchor(direction=-1)

    def _copy_selection(self) -> None:
        sel = self.table.selectionModel()
        if sel is None or not sel.hasSelection():
            return
        full_rows = [
            idx.row()
            for idx in sel.selectedRows()
            if sel.isRowSelected(idx.row(), idx.parent())
        ]
        if full_rows:
            lines: list[str] = []
            for row in sorted(set(full_rows)):
                cols = [
                    (
                        self._current_model.index(row, col).data(Qt.DisplayRole)
                        if self._current_model
                        else ""
                    )
                    for col in range(4)
                ]
                line = "\t".join("" if c is None else str(c) for c in cols)
                lines.append(line)
            QGuiApplication.clipboard().setText("\n".join(lines))
            return
        idx = self.table.currentIndex()
        if not idx.isValid():
            return
        text = idx.data(Qt.DisplayRole)
        QGuiApplication.clipboard().setText("" if text is None else str(text))

    def _cut_selection(self) -> None:
        idx = self.table.currentIndex()
        if not idx.isValid() or idx.column() != 2:
            return
        self._copy_selection()
        if self._current_model:
            self._current_model.setData(idx, "", Qt.EditRole)

    def _paste_selection(self) -> None:
        idx = self.table.currentIndex()
        if not idx.isValid() or idx.column() != 2:
            return
        if not self._current_model:
            return
        text = QGuiApplication.clipboard().text()
        rows = self._selected_rows()
        if len(rows) <= 1:
            self._current_model.setData(idx, text, Qt.EditRole)
            return
        stack = self._current_model.undo_stack
        stack.beginMacro("Set translation for selection")
        try:
            for row in rows:
                model_index = self._current_model.index(row, 2)
                self._current_model.setData(model_index, text, Qt.EditRole)
        finally:
            stack.endMacro()

    def _toggle_wrap_text(self, checked: bool) -> None:
        self._wrap_text_user = bool(checked)
        self._apply_wrap_mode()
        self._persist_preferences()

    def _apply_wrap_mode(self) -> None:
        effective = self._wrap_text_user and not self._large_file_mode
        if self._wrap_text != effective:
            self._wrap_text = effective
            self.table.setWordWrap(self._wrap_text)
            self._apply_row_height_mode()
            self._clear_row_height_cache()
            if self._wrap_text:
                self._schedule_row_resize()
        if getattr(self, "act_wrap", None):
            self.act_wrap.blockSignals(True)
            try:
                self.act_wrap.setChecked(self._wrap_text)
            finally:
                self.act_wrap.blockSignals(False)
            if self._large_file_mode:
                self.act_wrap.setToolTip("Wrap disabled by large-file mode")
            else:
                self.act_wrap.setToolTip("Wrap long strings in table")

    def _update_large_file_mode(self) -> None:
        active = self._is_large_file() if self._large_text_optimizations else False
        if active != self._large_file_mode:
            self._large_file_mode = active
            self._apply_wrap_mode()
            self._apply_text_visual_options()

    def _apply_row_height_mode(self) -> None:
        header = self.table.verticalHeader()
        header.setDefaultSectionSize(self._default_row_height)
        if hasattr(self.table, "setUniformRowHeights"):
            # Available on some Qt/PySide builds; avoid AttributeError on others.
            self.table.setUniformRowHeights(not self._wrap_text)
        if self._wrap_text:
            header.setSectionResizeMode(QHeaderView.Interactive)
        else:
            # No-wrap uses fixed row height to avoid sizeHint churn.
            header.setSectionResizeMode(QHeaderView.Fixed)

    def _text_visual_options_table(self) -> tuple[bool, bool, bool]:
        show_ws = self._visual_whitespace
        highlight = self._visual_highlight
        if self._large_file_mode and self._large_text_optimizations:
            show_ws = False
            highlight = False
        return show_ws, highlight, self._large_text_optimizations

    def _text_visual_options_detail(self) -> tuple[bool, bool, bool]:
        return (
            self._visual_whitespace,
            self._visual_highlight,
            self._large_text_optimizations,
        )

    def _apply_text_visual_options(self) -> None:
        self._apply_detail_whitespace_options()
        for highlighter in (
            self._detail_source_highlighter,
            self._detail_translation_highlighter,
        ):
            if highlighter:
                highlighter.rehighlight()
        if self.table.viewport():
            self.table.viewport().update()

    def _apply_detail_whitespace_options(self) -> None:
        show_ws, _highlight, optimize = self._text_visual_options_detail()
        for editor in (self._detail_source, self._detail_translation):
            if not editor:
                continue
            if optimize and editor.document().characterCount() >= MAX_VISUAL_CHARS:
                apply_ws = False
            else:
                apply_ws = show_ws
            option = editor.document().defaultTextOption()
            flags = option.flags()
            if apply_ws:
                flags |= (
                    QTextOption.ShowTabsAndSpaces
                    | QTextOption.ShowLineAndParagraphSeparators
                )
            else:
                flags &= ~(
                    QTextOption.ShowTabsAndSpaces
                    | QTextOption.ShowLineAndParagraphSeparators
                )
            option.setFlags(flags)
            editor.document().setDefaultTextOption(option)

    def _toggle_prompt_on_exit(self, checked: bool) -> None:
        self._prompt_write_on_exit = bool(checked)
        self._persist_preferences()

    def _persist_preferences(self) -> None:
        geometry = ""
        try:
            geometry = bytes(self.saveGeometry().toBase64()).decode("ascii")
        except Exception:
            geometry = ""
        prefs = {
            "prompt_write_on_exit": self._prompt_write_on_exit,
            "wrap_text": self._wrap_text_user,
            "large_text_optimizations": self._large_text_optimizations,
            "last_root": str(self._root),
            "last_locales": list(self._selected_locales),
            "window_geometry": geometry,
            "default_root": self._default_root,
            "search_scope": self._search_scope,
            "replace_scope": self._replace_scope,
            "__extras__": dict(self._prefs_extras),
        }
        with contextlib.suppress(Exception):
            _save_preferences(prefs, self._root)
        if self._default_root:
            try:
                global_prefs = _load_preferences(None)
                global_prefs["default_root"] = self._default_root
                _save_preferences(global_prefs, None)
            except Exception:
                pass

    def _on_model_data_changed(self, top_left, bottom_right, roles=None) -> None:
        if not self._current_model:
            return
        current = self.table.currentIndex()
        if not current.isValid():
            self._update_status_combo_from_selection()
            return
        row = current.row()
        if top_left.row() <= row <= bottom_right.row() and (
            roles is None or Qt.EditRole in roles or Qt.DisplayRole in roles
        ):
            self._update_status_combo_from_selection()
            if self._wrap_text:
                self._clear_row_height_cache(
                    range(top_left.row(), bottom_right.row() + 1)
                )
                self._schedule_row_resize()
            if (
                self._detail_panel.isVisible()
                and not self._detail_translation.hasFocus()
            ):
                self._sync_detail_editors()

    def _on_selection_changed(self, current, previous) -> None:
        perf_trace = PERF_TRACE
        perf_start = perf_trace.start("selection")
        try:
            if previous is not None and previous.isValid():
                self._commit_detail_translation(previous)
            self._update_status_combo_from_selection()
            if self._detail_panel.isVisible():
                self._sync_detail_editors()
            self._update_status_bar()
            self._schedule_tm_update()
        finally:
            perf_trace.stop("selection", perf_start, items=1, unit="events")

    def _schedule_tm_update(self) -> None:
        if not self._tm_store:
            return
        if self._left_stack.currentIndex() != 1:
            return
        if self._tm_update_timer.isActive():
            self._tm_update_timer.stop()
        self._tm_update_timer.start()

    def _update_tm_apply_state(self) -> None:
        self._tm_apply_btn.setEnabled(bool(self._tm_list.selectedItems()))

    def _on_tm_filters_changed(self) -> None:
        self._tm_min_score = int(self._tm_score_spin.value())
        self._tm_origin_project = bool(self._tm_origin_project_cb.isChecked())
        self._tm_origin_import = bool(self._tm_origin_import_cb.isChecked())
        self._prefs_extras["TM_MIN_SCORE"] = str(self._tm_min_score)
        self._prefs_extras["TM_ORIGIN_PROJECT"] = (
            "true" if self._tm_origin_project else "false"
        )
        self._prefs_extras["TM_ORIGIN_IMPORT"] = (
            "true" if self._tm_origin_import else "false"
        )
        self._persist_preferences()
        self._update_tm_suggestions()

    def _filter_tm_matches(self, matches: list[TMMatch]) -> list[TMMatch]:
        filtered: list[TMMatch] = []
        for match in matches:
            if match.score < self._tm_min_score:
                continue
            if match.origin == "project":
                if not self._tm_origin_project:
                    continue
            else:
                if not self._tm_origin_import:
                    continue
            filtered.append(match)
        return filtered

    def _current_tm_lookup(self) -> tuple[str, str] | None:
        if not (self._current_model and self._current_pf):
            return None
        current = self.table.currentIndex()
        if not current.isValid():
            return None
        source_index = self._current_model.index(current.row(), 1)
        source_text = str(source_index.data(Qt.EditRole) or "")
        if not source_text.strip():
            return None
        locale = self._locale_for_path(self._current_pf.path)
        if not locale:
            return None
        return source_text, locale

    def _apply_tm_selection(self) -> None:
        if not (self._current_model and self._current_pf):
            return
        items = self._tm_list.selectedItems()
        if not items:
            return
        match = items[0].data(Qt.UserRole)
        if not isinstance(match, TMMatch):
            return
        current = self.table.currentIndex()
        if not current.isValid():
            return
        value_index = self._current_model.index(current.row(), 2)
        self._current_model.setData(value_index, match.target_text, Qt.EditRole)
        status_index = self._current_model.index(current.row(), 3)
        self._current_model.setData(status_index, Status.FOR_REVIEW, Qt.EditRole)
        self._update_status_combo_from_selection()

    def _update_tm_suggestions(self) -> None:
        if not self._tm_store:
            return
        if self._left_stack.currentIndex() != 1:
            return
        if not self._tm_origin_project and not self._tm_origin_import:
            self._tm_list.clear()
            self._tm_status_label.setText("No TM origins enabled.")
            self._tm_apply_btn.setEnabled(False)
            return
        lookup = self._current_tm_lookup()
        if lookup is None:
            self._tm_list.clear()
            self._tm_status_label.setText("Select a row to see TM suggestions.")
            self._tm_apply_btn.setEnabled(False)
            return
        source_text, locale = lookup
        self._flush_tm_updates(paths=[self._current_pf.path])
        cache_key = (
            source_text,
            self._tm_source_locale,
            locale,
            self._tm_min_score,
            self._tm_origin_project,
            self._tm_origin_import,
        )
        matches = self._tm_cache.get(cache_key)
        if matches is not None:
            self._show_tm_matches(matches)
            return
        self._tm_status_label.setText("Searching TM...")
        self._tm_list.clear()
        self._tm_apply_btn.setEnabled(False)
        self._start_tm_query(cache_key)

    def _start_tm_query(self, cache_key: tuple[str, str, str, int, bool, bool]) -> None:
        if not self._tm_store or self._tm_query_pool is None:
            return
        if (
            self._tm_query_key == cache_key
            and self._tm_query_future is not None
            and not self._tm_query_future.done()
        ):
            return
        self._tm_query_key = cache_key
        (
            source_text,
            source_locale,
            target_locale,
            min_score,
            origin_project,
            origin_import,
        ) = cache_key
        origins = []
        if origin_project:
            origins.append("project")
        if origin_import:
            origins.append("import")
        self._tm_query_future = self._tm_query_pool.submit(
            TMStore.query_path,
            self._tm_store.db_path,
            source_text,
            source_locale=source_locale,
            target_locale=target_locale,
            limit=12,
            min_score=min_score,
            origins=origins,
        )
        if not self._tm_query_timer.isActive():
            self._tm_query_timer.start()

    def _poll_tm_query(self) -> None:
        future = self._tm_query_future
        cache_key = self._tm_query_key
        if future is None:
            self._tm_query_timer.stop()
            return
        if not future.done():
            return
        self._tm_query_timer.stop()
        self._tm_query_future = None
        self._tm_query_key = None
        if cache_key is None:
            return
        try:
            matches = future.result()
        except Exception:
            self._tm_status_label.setText("TM lookup failed.")
            self._tm_apply_btn.setEnabled(False)
            return
        self._tm_cache[cache_key] = matches
        if len(self._tm_cache) > self._tm_cache_limit:
            self._tm_cache.popitem(last=False)
        lookup = self._current_tm_lookup()
        if lookup is None:
            return
        current_key = (
            lookup[0],
            self._tm_source_locale,
            lookup[1],
            self._tm_min_score,
            self._tm_origin_project,
            self._tm_origin_import,
        )
        if current_key != cache_key:
            return
        self._show_tm_matches(matches)

    def _show_tm_matches(self, matches: list[TMMatch]) -> None:
        self._tm_list.clear()
        if not matches:
            self._tm_status_label.setText("No TM matches found.")
            self._tm_apply_btn.setEnabled(False)
            return
        filtered = self._filter_tm_matches(matches)
        if not filtered:
            self._tm_status_label.setText("No TM matches (filtered).")
            self._tm_apply_btn.setEnabled(False)
            return
        self._tm_status_label.setText("TM suggestions")
        for match in filtered:
            item = QListWidgetItem(self._format_tm_item(match))
            item.setData(Qt.UserRole, match)
            item.setToolTip(self._tooltip_html(match.target_text))
            self._tm_list.addItem(item)
        self._tm_apply_btn.setEnabled(bool(self._tm_list.selectedItems()))

    def _format_tm_item(self, match: TMMatch) -> str:
        origin = "project" if match.origin == "project" else "import"
        target_preview = self._truncate_text(match.target_text, 80)
        return f"{match.score:>3}% · {origin}: {target_preview}"

    def _truncate_text(self, text: str, limit: int) -> str:
        if len(text) <= limit:
            return text
        return text[: max(0, limit - 1)] + "…"

    def _tooltip_html(self, text: str) -> str:
        escaped = html.escape(text)
        return f"<span style=\"white-space: pre-wrap;\">{escaped}</span>"

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        if self._detail_panel.isVisible():
            self._toggle_detail_panel(True)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self.table.model():
            self._apply_table_layout()
            if self._wrap_text and self._is_large_file():
                self._schedule_row_resize()
        if self.replace_toolbar.isVisible():
            self._align_replace_bar()

    def _update_status_combo_from_selection(self) -> None:
        if not self._current_model:
            self._set_status_combo(None)
            return
        rows = self._selected_rows()
        if not rows:
            self._set_status_combo(None)
            return
        statuses = {self._current_model.status_for_row(row) for row in rows}
        statuses.discard(None)
        if len(statuses) == 1:
            self._set_status_combo(statuses.pop())
        else:
            self._set_status_combo(None)

    def _set_status_combo(self, status: Status | None) -> None:
        self._updating_status_combo = True
        try:
            if status is None:
                self.status_combo.setEnabled(bool(self._selected_rows()))
                self.status_combo.setCurrentIndex(-1)
                return
            self.status_combo.setEnabled(True)
            for i in range(self.status_combo.count()):
                if self.status_combo.itemData(i) == status:
                    self.status_combo.setCurrentIndex(i)
                    return
            self.status_combo.setCurrentIndex(-1)
        finally:
            self._updating_status_combo = False

    def _status_combo_changed(self, _index: int) -> None:
        if self._updating_status_combo:
            return
        if not self._current_model:
            return
        status = self.status_combo.currentData()
        if status is None:
            return
        rows = self._selected_rows()
        if not rows:
            return
        if len(rows) == 1:
            model_index = self._current_model.index(rows[0], 3)
            self._current_model.setData(model_index, status, Qt.EditRole)
            return
        if not any(self._current_model.status_for_row(row) != status for row in rows):
            return
        stack = self._current_model.undo_stack
        stack.beginMacro("Set status for selection")
        try:
            for row in rows:
                model_index = self._current_model.index(row, 3)
                self._current_model.setData(model_index, status, Qt.EditRole)
        finally:
            stack.endMacro()

    def _set_saved_status(self) -> None:
        self._last_saved_text = time.strftime("Saved %H:%M:%S")
        self._update_status_bar()

    def _selected_rows(self) -> list[int]:
        sel = self.table.selectionModel()
        if sel is None:
            return []
        current = self.table.currentIndex()
        if current.isValid() and not sel.isSelected(current):
            return [current.row()]
        rows = {idx.row() for idx in sel.selectedRows()}
        if not rows:
            rows = {idx.row() for idx in sel.selectedIndexes()}
        return sorted(rows)

    def _update_status_bar(self) -> None:
        parts: list[str] = []
        if self._last_saved_text:
            parts.append(self._last_saved_text)
        if self._search_progress_text:
            parts.append(self._search_progress_text)
        if self._current_model:
            idx = self.table.currentIndex()
            if idx.isValid():
                parts.append(f"Row {idx.row() + 1} / {self._current_model.rowCount()}")
        if self._current_pf:
            try:
                rel = self._current_pf.path.relative_to(self._root)
                parts.append(str(rel))
            except ValueError:
                parts.append(str(self._current_pf.path))
        if not parts:
            parts.append("Ready")
        self.statusBar().showMessage(" | ".join(parts))
        self._update_scope_indicators()

    def _update_scope_indicators(self) -> None:
        if not self._search_scope_widget or not self._replace_scope_widget:
            return
        search_active = bool(self.search_edit.text().strip())
        replace_active = self.replace_toolbar.isVisible()
        self._set_scope_indicator(
            self._search_scope_widget,
            self._search_scope_icon,
            self._search_scope,
            search_active,
            "Search scope",
        )
        self._set_scope_indicator(
            self._replace_scope_widget,
            self._replace_scope_icon,
            self._replace_scope,
            replace_active,
            "Replace scope",
        )

    def _set_scope_indicator(
        self,
        widget: QWidget,
        icon_label: QLabel,
        scope: str,
        active: bool,
        title: str,
    ) -> None:
        if not active:
            widget.setVisible(False)
            return
        icon = self._scope_icon(scope)
        icon_label.setPixmap(icon.pixmap(14, 14))
        widget.setToolTip(f"{title}: {scope.title()}")
        widget.setVisible(True)

    def _apply_status_to_selection(self, status: Status, label: str) -> None:
        if not (self._current_pf and self._current_model):
            return
        rows = self._selected_rows()
        if not rows:
            return
        if len(rows) == 1:
            model_index = self._current_model.index(rows[0], 3)
            self._current_model.setData(model_index, status, Qt.EditRole)
            self._update_status_combo_from_selection()
            return
        if not any(self._current_model.status_for_row(row) != status for row in rows):
            return
        stack = self._current_model.undo_stack
        stack.beginMacro(label)
        try:
            for row in rows:
                model_index = self._current_model.index(row, 3)
                self._current_model.setData(model_index, status, Qt.EditRole)
        finally:
            stack.endMacro()
        self._update_status_combo_from_selection()

    def _mark_proofread(self) -> None:
        self._apply_status_to_selection(Status.PROOFREAD, "Mark proofread")

    def _mark_translated(self) -> None:
        self._apply_status_to_selection(Status.TRANSLATED, "Mark translated")

    def _mark_for_review(self) -> None:
        self._apply_status_to_selection(Status.FOR_REVIEW, "Mark for review")

    def closeEvent(self, event) -> None:  # noqa: N802
        if self._merge_active:
            event.ignore()
            return
        self._write_cache_current()
        if self._prompt_write_on_exit:
            files = self._draft_files()
            if files:
                rel_files = [str(p.relative_to(self._root)) for p in files]
                dialog = SaveFilesDialog(rel_files, self)
                dialog.exec()
                decision = dialog.choice()
                if decision == "cancel":
                    event.ignore()
                    return
                if decision == "write":
                    self._save_all_files(files)
        if not self._write_cache_current():
            event.ignore()
            return
        self._stop_timers()
        with contextlib.suppress(Exception):
            self._flush_tm_updates()
        self._shutdown_tm_workers()
        if self._tm_store is not None:
            with contextlib.suppress(Exception):
                self._tm_store.close()
        if self._tree_width_timer.isActive():
            self._tree_width_timer.stop()
            self._prefs_extras["TREE_PANEL_WIDTH"] = str(max(60, self._tree_last_width))
        self._persist_preferences()
        event.accept()

    def _shutdown_tm_workers(self) -> None:
        if self._tm_query_future is not None:
            with contextlib.suppress(Exception):
                self._tm_query_future.cancel()
        self._tm_query_future = None
        self._tm_query_key = None
        if self._tm_query_pool is None:
            self._tm_query_pool = None
        else:
            with contextlib.suppress(Exception):
                self._tm_query_pool.shutdown(wait=False, cancel_futures=True)
            self._tm_query_pool = None
        if self._tm_rebuild_future is not None:
            with contextlib.suppress(Exception):
                self._tm_rebuild_future.cancel()
        self._tm_rebuild_future = None
        if self._tm_rebuild_pool is None:
            return
        with contextlib.suppress(Exception):
            self._tm_rebuild_pool.shutdown(wait=False, cancel_futures=True)
        self._tm_rebuild_pool = None

    def _stop_timers(self) -> None:
        timers = [
            self._search_timer,
            self._row_resize_timer,
            self._scroll_idle_timer,
            self._tooltip_timer,
            self._tree_width_timer,
            self._post_locale_timer,
            self._tm_update_timer,
            self._tm_flush_timer,
            self._tm_query_timer,
            self._tm_rebuild_timer,
        ]
        if self._migration_timer is not None:
            timers.append(self._migration_timer)
        for timer in timers:
            if timer.isActive():
                timer.stop()
