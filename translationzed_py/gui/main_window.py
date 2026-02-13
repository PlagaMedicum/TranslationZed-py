from __future__ import annotations

import contextlib
import html
import os
import re
import shutil
import sys
import time
import traceback
from collections import OrderedDict
from collections.abc import Callable, Iterable, Mapping, Sequence
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from typing import Literal

import xxhash
from PySide6.QtCore import (
    QByteArray,
    QEvent,
    QEventLoop,
    QItemSelectionModel,
    QModelIndex,
    QPoint,
    QRegularExpression,
    Qt,
    QTimer,
    QUrl,
)
from PySide6.QtGui import (
    QAction,
    QColor,
    QCursor,
    QDesktopServices,
    QGuiApplication,
    QIcon,
    QKeySequence,
    QTextCharFormat,
    QTextOption,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
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
    QTextEdit,
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
from translationzed_py.core.conflict_service import (
    ConflictMergeRow as _ConflictMergeRow,
)
from translationzed_py.core.conflict_service import (
    ConflictPersistCallbacks as _ConflictPersistCallbacks,
)
from translationzed_py.core.conflict_service import (
    ConflictResolution as _ConflictResolution,
)
from translationzed_py.core.conflict_service import (
    ConflictWorkflowService as _ConflictWorkflowService,
)
from translationzed_py.core.en_hash_cache import compute as _compute_en_hashes
from translationzed_py.core.en_hash_cache import read as _read_en_hash_cache
from translationzed_py.core.en_hash_cache import write as _write_en_hash_cache
from translationzed_py.core.file_workflow import (
    FileWorkflowService as _FileWorkflowService,
)
from translationzed_py.core.file_workflow import (
    OpenFileCallbacks as _OpenFileCallbacks,
)
from translationzed_py.core.file_workflow import (
    SaveCurrentCallbacks as _SaveCurrentCallbacks,
)
from translationzed_py.core.file_workflow import (
    SaveFromCacheCallbacks as _SaveFromCacheCallbacks,
)
from translationzed_py.core.file_workflow import (
    SaveFromCacheParseError as _SaveFromCacheParseError,
)
from translationzed_py.core.model import STATUS_ORDER, Status
from translationzed_py.core.preferences_service import (
    PreferencesService as _PreferencesService,
)
from translationzed_py.core.project_session import (
    CacheMigrationBatchCallbacks as _CacheMigrationBatchCallbacks,
)
from translationzed_py.core.project_session import (
    CacheMigrationScheduleCallbacks as _CacheMigrationScheduleCallbacks,
)
from translationzed_py.core.project_session import (
    LocaleResetPlan as _LocaleResetPlan,
)
from translationzed_py.core.project_session import (
    PostLocaleStartupPlan as _PostLocaleStartupPlan,
)
from translationzed_py.core.project_session import (
    ProjectSessionService as _ProjectSessionService,
)
from translationzed_py.core.project_session import (
    TreeRebuildPlan as _TreeRebuildPlan,
)
from translationzed_py.core.render_workflow_service import (
    RenderWorkflowService as _RenderWorkflowService,
)
from translationzed_py.core.save_exit_flow import (
    SaveExitFlowService as _SaveExitFlowService,
)
from translationzed_py.core.saver import save
from translationzed_py.core.search import Match as _SearchMatch
from translationzed_py.core.search import SearchField as _SearchField
from translationzed_py.core.search import SearchRow as _SearchRow
from translationzed_py.core.search import iter_matches as _iter_search_matches
from translationzed_py.core.search_replace_service import (
    ReplaceAllFileApplyCallbacks as _ReplaceAllFileApplyCallbacks,
)
from translationzed_py.core.search_replace_service import (
    ReplaceAllFileCountCallbacks as _ReplaceAllFileCountCallbacks,
)
from translationzed_py.core.search_replace_service import (
    ReplaceAllFileParseError as _ReplaceAllFileParseError,
)
from translationzed_py.core.search_replace_service import (
    ReplaceAllRowsCallbacks as _ReplaceAllRowsCallbacks,
)
from translationzed_py.core.search_replace_service import (
    ReplaceCurrentRowCallbacks as _ReplaceCurrentRowCallbacks,
)
from translationzed_py.core.search_replace_service import (
    ReplaceRequest as _ReplaceRequest,
)
from translationzed_py.core.search_replace_service import (
    ReplaceRequestError as _ReplaceRequestError,
)
from translationzed_py.core.search_replace_service import (
    SearchReplaceService as _SearchReplaceService,
)
from translationzed_py.core.search_replace_service import (
    SearchRowsCacheStamp as _SearchRowsCacheStamp,
)
from translationzed_py.core.search_replace_service import (
    SearchRowsCacheStampCallbacks as _SearchRowsCacheStampCallbacks,
)
from translationzed_py.core.search_replace_service import (
    SearchRowsFileCallbacks as _SearchRowsFileCallbacks,
)
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
from translationzed_py.core.tm_import_sync import (
    TMImportSyncReport,
)
from translationzed_py.core.tm_query import (
    TMQueryKey,
    TMQueryPolicy,
)
from translationzed_py.core.tm_rebuild import (
    TMRebuildResult,
)
from translationzed_py.core.tm_store import TMMatch, TMStore
from translationzed_py.core.tm_workflow_service import (
    TMSelectionPlan as _TMSelectionPlan,
)
from translationzed_py.core.tm_workflow_service import (
    TMWorkflowService as _TMWorkflowService,
)

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
from .theme import THEME_SYSTEM as _THEME_SYSTEM
from .theme import apply_theme as _apply_app_theme
from .theme import normalize_theme_mode as _normalize_theme_mode

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


def _int_from_pref(
    value: object, default: int, *, min_value: int, max_value: int
) -> int:
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


# Avoid blocking UI by deferring detail-panel loads for huge strings.
_DETAIL_LAZY_THRESHOLD = 100_000


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

    def preview_at(self, idx: int, limit: int) -> str:
        entries = self._entries
        if hasattr(entries, "preview_at"):
            try:
                return entries.preview_at(idx, limit)
            except Exception:
                return ""
        value = entries[idx].value
        if not value:
            return ""
        if limit <= 0:
            return ""
        return value[:limit]


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
        self._preferences_service = _PreferencesService()
        self._smoke = os.environ.get("TZP_SMOKE", "") == "1"
        self._test_mode = _in_test_mode()
        _patch_message_boxes_for_tests()
        startup_root = self._preferences_service.resolve_startup_root(
            project_root=project_root
        )
        if startup_root.root is not None:
            self._root = startup_root.root
            self._default_root = startup_root.default_root
        elif startup_root.requires_picker:
            picked = QFileDialog.getExistingDirectory(
                self, "Select Project Root", str(Path.cwd())
            )
            if not picked:
                self._startup_aborted = True
                return
            self._root = Path(picked).resolve()
            self._default_root = str(self._root)
            self._preferences_service.persist_default_root(self._default_root)
        if not self._root.exists():
            QMessageBox.warning(self, "Invalid project root", str(self._root))
            self._startup_aborted = True
            return
        self.setWindowTitle(f"TranslationZed-Py – {self._root}")
        self._locales: dict[str, LocaleMeta] = {}
        self._selected_locales: list[str] = []
        self._current_encoding = "utf-8"
        self._app_config = _load_app_config(self._root)
        self._project_session_service = _ProjectSessionService(
            cache_dir=self._app_config.cache_dir,
            cache_ext=self._app_config.cache_ext,
            translation_ext=self._app_config.translation_ext,
            has_drafts=_read_has_drafts_from_path,
            read_last_opened=_read_last_opened_from_path,
        )
        self._render_workflow_service = _RenderWorkflowService()
        self._file_workflow_service = _FileWorkflowService()
        self._conflict_workflow_service = _ConflictWorkflowService()
        self._search_replace_service = _SearchReplaceService()
        self._save_exit_flow_service = _SaveExitFlowService()
        self._current_pf = None  # type: translationzed_py.core.model.ParsedFile | None
        self._current_model: TranslationModel | None = None
        self._opened_files: set[Path] = set()
        self._cache_map: Mapping[int, CacheEntry] = {}
        self._conflict_files: dict[Path, dict[str, str]] = {}
        self._conflict_sources: dict[Path, dict[str, str]] = {}
        self._conflict_notified: set[Path] = set()
        self._skip_conflict_check = False
        self._skip_cache_write = False
        self._open_flow_depth = 0
        self._files_by_locale: dict[str, list[Path]] = {}
        self._en_cache: dict[Path, ParsedFile] = {}
        self._child_windows: list[MainWindow] = []
        self._tm_store: TMStore | None = None
        self._tm_workflow = _TMWorkflowService(cache_limit=128)
        self._tm_source_locale = "EN"
        self._tm_query_pool: ThreadPoolExecutor | None = None
        self._tm_query_future: Future[list[TMMatch]] | None = None
        self._tm_query_key: TMQueryKey | None = None
        self._tm_rebuild_pool: ThreadPoolExecutor | None = None
        self._tm_rebuild_future: Future[TMRebuildResult] | None = None
        self._tm_rebuild_locales: list[str] = []
        self._tm_rebuild_interactive = False
        self._tm_bootstrap_pending = False

        if not self._smoke and not self._check_en_hash_cache():
            self._startup_aborted = True
            return
        normalized_prefs = self._preferences_service.load_normalized_preferences(
            fallback_default_root=self._default_root,
            fallback_last_root=str(self._root),
            default_tm_import_dir=str(self._default_tm_import_dir()),
            test_mode=self._test_mode,
        )
        self._prompt_write_on_exit = normalized_prefs.prompt_write_on_exit
        self._wrap_text_user = normalized_prefs.wrap_text
        self._wrap_text = self._wrap_text_user
        self._large_text_optimizations = normalized_prefs.large_text_optimizations
        self._default_root = normalized_prefs.default_root
        self._search_scope = normalized_prefs.search_scope
        self._replace_scope = normalized_prefs.replace_scope
        self._search_scope_widget = None
        self._search_scope_action = None
        self._search_scope_icon = None
        self._replace_scope_widget = None
        self._replace_scope_action = None
        self._replace_scope_icon = None
        self._last_locales = normalized_prefs.last_locales
        self._last_root = normalized_prefs.last_root
        self._prefs_extras = normalized_prefs.extras
        self._theme_mode = _normalize_theme_mode(
            self._prefs_extras.get("UI_THEME_MODE"), default=_THEME_SYSTEM
        )
        self._apply_theme_mode(self._theme_mode, persist=False)
        self._system_theme_sync_connected = False
        self._connect_system_theme_sync()
        self._search_case_sensitive = _bool_from_pref(
            self._prefs_extras.get("SEARCH_CASE_SENSITIVE"), False
        )
        self._tm_min_score = _int_from_pref(
            self._prefs_extras.get("TM_MIN_SCORE"), 50, min_value=5, max_value=100
        )
        self._tm_origin_project = _bool_from_pref(
            self._prefs_extras.get("TM_ORIGIN_PROJECT"), True
        )
        self._tm_origin_import = _bool_from_pref(
            self._prefs_extras.get("TM_ORIGIN_IMPORT"), True
        )
        self._tm_import_dir = normalized_prefs.tm_import_dir
        geom = normalized_prefs.window_geometry
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
        self._detail_source_chars: int | None = None
        self._detail_translation_chars: int | None = None
        self._large_file_mode = False
        self._render_heavy = False
        self._preview_limit = 800
        # Derive render-heavy cutoff from preview size to avoid extra tuning knobs.
        self._render_heavy_threshold = self._preview_limit * 3
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
        self._pending_post_locale_plan: _PostLocaleStartupPlan | None = None
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
        regex_layout.setSpacing(2)
        regex_layout.addWidget(self.regex_check)
        regex_layout.addWidget(self.regex_help)
        self.search_case_btn = QToolButton(self)
        self.search_case_btn.setCheckable(True)
        self.search_case_btn.setAutoRaise(True)
        self.search_case_btn.setText("Aa")
        self.search_case_btn.setChecked(self._search_case_sensitive)
        self.search_case_btn.toggled.connect(self._toggle_search_case_sensitive)
        regex_layout.addWidget(self.search_case_btn)
        self._update_case_toggle_ui()
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
            tuple[Path, bool, bool], tuple[_SearchRowsCacheStamp, list[_SearchRow]]
        ] = OrderedDict()
        self._search_cache_max = 64
        self._search_cache_row_limit = 5000
        self._search_panel_result_limit = 200
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
        self._row_resize_budget_ms = 8.0
        self._row_resize_cursor: int | None = None
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
        tree_plan = self._project_session_service.build_tree_rebuild_plan(
            selected_locales=self._selected_locales,
            resize_splitter=False,
        )
        self._rebuild_tree_for_selected_locales(tree_plan=tree_plan)
        self.tree.expanded.connect(self._on_tree_expanded)
        # prevent in-place renaming on double-click; we use double-click to open
        self.tree.setEditTriggers(QAbstractItemView.NoEditTriggers)
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
        tm_score_label = QLabel("Min score", self._tm_panel)
        tm_score_label.setToolTip("Minimum TM score threshold (5..100)")
        tm_filter_row.addWidget(tm_score_label)
        self._tm_score_spin = QSpinBox(self._tm_panel)
        self._tm_score_spin.setRange(5, 100)
        self._tm_score_spin.setValue(self._tm_min_score)
        self._tm_score_spin.setSuffix("%")
        self._tm_score_spin.setToolTip(
            "Lower score increases recall and returns more neighboring suggestions"
        )
        self._tm_score_spin.valueChanged.connect(self._on_tm_filters_changed)
        tm_filter_row.addWidget(self._tm_score_spin)
        tm_filter_row.addStretch(1)
        self._tm_origin_project_cb = QCheckBox("Project", self._tm_panel)
        self._tm_origin_project_cb.setToolTip("Include project TM entries")
        self._tm_origin_project_cb.setChecked(self._tm_origin_project)
        self._tm_origin_project_cb.toggled.connect(self._on_tm_filters_changed)
        tm_filter_row.addWidget(self._tm_origin_project_cb)
        self._tm_origin_import_cb = QCheckBox("Imported", self._tm_panel)
        self._tm_origin_import_cb.setToolTip("Include imported TM entries")
        self._tm_origin_import_cb.setChecked(self._tm_origin_import)
        self._tm_origin_import_cb.toggled.connect(self._on_tm_filters_changed)
        tm_filter_row.addWidget(self._tm_origin_import_cb)
        self._tm_rebuild_side_btn = QToolButton(self._tm_panel)
        self._tm_rebuild_side_btn.setAutoRaise(True)
        self._tm_rebuild_side_btn.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload)
        )
        self._tm_rebuild_side_btn.setToolTip("Rebuild project TM for selected locales")
        self._tm_rebuild_side_btn.clicked.connect(self._rebuild_tm_selected)
        tm_filter_row.addWidget(self._tm_rebuild_side_btn)
        self._tm_list = QListWidget(self._tm_panel)
        self._tm_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self._tm_list.itemSelectionChanged.connect(self._update_tm_apply_state)
        self._tm_list.itemDoubleClicked.connect(self._apply_tm_selection)
        self._tm_source_preview = QPlainTextEdit(self._tm_panel)
        self._tm_source_preview.setReadOnly(True)
        self._tm_source_preview.setPlaceholderText("TM source (full text)")
        self._tm_source_preview.setMaximumHeight(84)
        self._tm_target_preview = QPlainTextEdit(self._tm_panel)
        self._tm_target_preview.setReadOnly(True)
        self._tm_target_preview.setPlaceholderText("TM translation (full text)")
        self._tm_target_preview.setMaximumHeight(84)
        self._tm_apply_btn = QPushButton("Apply", self._tm_panel)
        self._tm_apply_btn.setEnabled(False)
        self._tm_apply_btn.clicked.connect(self._apply_tm_selection)
        tm_layout.addWidget(self._tm_status_label)
        tm_layout.addLayout(tm_filter_row)
        tm_layout.addWidget(self._tm_list)
        tm_layout.addWidget(QLabel("Source", self._tm_panel))
        tm_layout.addWidget(self._tm_source_preview)
        tm_layout.addWidget(QLabel("Translation", self._tm_panel))
        tm_layout.addWidget(self._tm_target_preview)
        tm_layout.addWidget(self._tm_apply_btn)
        self._left_stack.addWidget(self._tm_panel)

        self._search_panel = QWidget(self._left_panel)
        search_layout = QVBoxLayout(self._search_panel)
        search_layout.setContentsMargins(6, 0, 6, 6)
        search_layout.setSpacing(6)
        self._search_status_label = QLabel(
            "Press Enter in the search box to populate results.",
            self._search_panel,
        )
        self._search_status_label.setWordWrap(True)
        self._search_results_list = QListWidget(self._search_panel)
        self._search_results_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self._search_results_list.itemActivated.connect(self._open_search_result_item)
        self._search_results_list.itemClicked.connect(self._open_search_result_item)
        search_layout.addWidget(self._search_status_label)
        search_layout.addWidget(self._search_results_list)
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
        # Use app font for tooltips to avoid table-specific font scaling.
        QToolTip.setFont(QApplication.font())
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
        detail_counter_row = QHBoxLayout()
        detail_counter_row.setContentsMargins(0, 0, 0, 0)
        detail_counter_row.setSpacing(4)
        self._detail_inline_toggle = QToolButton(self._detail_panel)
        self._detail_inline_toggle.setAutoRaise(True)
        self._detail_inline_toggle.setToolButtonStyle(Qt.ToolButtonIconOnly)
        self._detail_inline_toggle.clicked.connect(
            lambda: self.detail_toggle.setChecked(False)
        )
        self._detail_inline_toggle.setVisible(False)
        detail_counter_row.addWidget(self._detail_inline_toggle)
        detail_counter_row.addStretch(1)
        self._detail_counter_label = QLabel("", self._detail_panel)
        self._detail_counter_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._detail_counter_label.setToolTip(
            "Character counts: S = source, T = translation, Delta = T - S."
        )
        detail_counter_row.addWidget(self._detail_counter_label)
        detail_layout.addLayout(detail_counter_row)
        self._set_detail_char_counts(None, None)
        margins = detail_layout.contentsMargins()
        label_total = (
            self._detail_source_label.sizeHint().height()
            + self._detail_translation_label.sizeHint().height()
        )
        counter_height = self._detail_counter_label.sizeHint().height()
        self._detail_min_height = (
            margins.top()
            + margins.bottom()
            + label_total
            + counter_height
            + min_line_height * 2
            + detail_layout.spacing() * 4
        )
        self._detail_panel.setVisible(False)
        self._main_splitter.addWidget(self._detail_panel)
        self._main_splitter.setStretchFactor(0, 1)
        self._main_splitter.setStretchFactor(1, 0)

        tree_width = self._initial_tree_width(tree_plan.lazy_tree)
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
        show_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowUp)
        hide_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowDown)
        if visible:
            self.detail_toggle.setIcon(hide_icon)
            self.detail_toggle.setToolTip("Hide string editor")
            self._detail_inline_toggle.setIcon(hide_icon)
            self._detail_inline_toggle.setToolTip("Hide string editor")
            self._detail_inline_toggle.setVisible(True)
            self.detail_toggle.setVisible(False)
        else:
            self.detail_toggle.setIcon(show_icon)
            self.detail_toggle.setToolTip("Show string editor")
            self._detail_inline_toggle.setIcon(show_icon)
            self._detail_inline_toggle.setToolTip("Show string editor")
            self._detail_inline_toggle.setVisible(False)
            self.detail_toggle.setVisible(True)

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
        self._refresh_detail_translation_count()

    def _set_detail_char_counts(
        self,
        source_chars: int | None,
        translation_chars: int | None,
    ) -> None:
        self._detail_source_chars = source_chars
        self._detail_translation_chars = translation_chars
        if source_chars is None and translation_chars is None:
            self._detail_counter_label.setText("")
            return
        source_text = "—" if source_chars is None else str(max(0, source_chars))
        translation_text = (
            "—" if translation_chars is None else str(max(0, translation_chars))
        )
        delta_text = "n/a"
        if source_chars is not None and translation_chars is not None:
            delta_text = f"{translation_chars - source_chars:+d}"
        self._detail_counter_label.setText(
            f"S: {source_text} | T: {translation_text} | Delta: {delta_text}"
        )
        self._detail_counter_label.setToolTip(
            "Character counts: S = source, T = translation, Delta = T - S."
        )

    def _refresh_detail_translation_count(self) -> None:
        translation_chars = max(
            0, self._detail_translation.document().characterCount() - 1
        )
        self._set_detail_char_counts(self._detail_source_chars, translation_chars)

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
        self._set_detail_char_counts(len(source_text), len(value_text))
        self._apply_detail_whitespace_options()

    def _set_detail_pending(self, row: int) -> None:
        source_len: int | None = None
        value_len: int | None = None
        if self._current_model:
            source_len, value_len = self._current_model.text_lengths(row)
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
        self._set_detail_char_counts(source_len, value_len)
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
                self._set_detail_char_counts(None, None)
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
                self._set_detail_char_counts(None, None)
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
            self._set_detail_char_counts(len(source_text), len(value_text))
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

        selected_locales = self._project_session_service.resolve_requested_locales(
            requested_locales=selected_locales,
            last_locales=self._last_locales,
            available_locales=self._locales.keys(),
            smoke_mode=self._smoke,
        )
        if selected_locales is None:
            dialog = LocaleChooserDialog(
                selectable.values(), self, preselected=self._last_locales
            )
            if dialog.exec() != dialog.DialogCode.Accepted:
                self._selected_locales = []
                return
            selected_locales = dialog.selected_codes()
        plan = self._project_session_service.build_locale_selection_plan(
            requested_locales=selected_locales,
            available_locales=self._locales.keys(),
        )
        if plan is None:
            self._selected_locales = []
            return
        self._selected_locales = list(plan.selected_locales)
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

    def _runtime_root(self) -> Path:
        if getattr(sys, "frozen", False):
            return Path(sys.executable).resolve().parent
        return Path.cwd().resolve()

    def _default_tm_import_dir(self) -> Path:
        return (self._runtime_root() / ".tzp" / "tms").resolve()

    def _tm_import_dir_path(self) -> Path:
        raw = str(self._tm_import_dir).strip()
        if not raw:
            return self._default_tm_import_dir()
        return Path(raw).expanduser().resolve()

    def _pick_tmx_locales(
        self,
        path: Path,
        langs: set[str],
        *,
        interactive: bool,
        allow_skip_all: bool = False,
    ) -> tuple[tuple[str, str] | None, bool]:
        normalized = sorted(
            {
                self._normalize_tm_locale(lang)
                for lang in langs
                if self._normalize_tm_locale(lang)
            }
        )
        default_source = self._tm_source_locale.strip().upper()
        default_target = None
        if self._current_pf:
            default_target = self._locale_for_path(self._current_pf.path)
        if default_source and default_source in normalized and len(normalized) == 2:
            for lang in normalized:
                if lang != default_source:
                    return (default_source, lang), False
        if not interactive:
            return None, False
        choices = normalized or sorted(self._locales.keys())
        dialog = TmLanguageDialog(
            choices,
            parent=self,
            default_source=default_source or None,
            default_target=default_target,
            title=f"TM locale pair: {path.name}",
            allow_skip_all=allow_skip_all,
        )
        if dialog.exec() != dialog.DialogCode.Accepted:
            return None, dialog.skip_all_requested()
        source_locale = dialog.source_locale().strip().upper()
        target_locale = dialog.target_locale().strip().upper()
        if not source_locale or not target_locale:
            return None, False
        return (source_locale, target_locale), False

    def _normalize_tm_locale(self, raw: str) -> str:
        value = raw.strip().upper().replace("_", "-")
        if not value:
            return ""
        if value in self._locales:
            return value
        base = value.split("-", 1)[0].strip()
        if base in self._locales:
            return base
        return value

    def _sync_tm_import_folder(
        self,
        *,
        interactive: bool,
        only_paths: set[Path] | None = None,
        pending_only: bool = False,
        show_summary: bool = False,
    ) -> None:
        if not self._ensure_tm_store():
            return
        tm_dir = self._tm_import_dir_path()
        try:
            tm_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            if interactive:
                QMessageBox.warning(self, "TM import folder", str(exc))
            else:
                self.statusBar().showMessage(
                    f"TM import folder unavailable: {exc}", 5000
                )
            return
        report = self._tm_workflow.sync_import_folder(
            store=self._tm_store,
            tm_dir=tm_dir,
            resolve_locales=lambda path, langs: self._pick_tmx_locales(
                path,
                langs,
                interactive=interactive,
                allow_skip_all=interactive,
            ),
            only_paths=only_paths,
            pending_only=pending_only,
        )
        self._apply_tm_sync_report(
            report,
            interactive=interactive,
            show_summary=show_summary,
        )

    def _apply_tm_sync_report(
        self,
        report: TMImportSyncReport,
        *,
        interactive: bool,
        show_summary: bool,
    ) -> None:
        if report.changed:
            self._tm_workflow.clear_cache()
            if self._left_stack.currentIndex() == 1:
                self._schedule_tm_update()
        if interactive:
            parts = []
            if report.imported_files:
                parts.append(
                    " ".join(
                        [
                            f"Imported {len(report.imported_files)} file(s),",
                            f"{report.imported_segments} segment(s).",
                        ]
                    )
                )
            if report.zero_segment_files:
                parts.append(
                    " ".join(
                        [
                            f"{len(report.zero_segment_files)} file(s) imported with 0 segments:",
                            ", ".join(report.zero_segment_files[:3]),
                        ]
                    )
                )
            if report.unresolved_files:
                parts.append(
                    " ".join(
                        [
                            f"{len(report.unresolved_files)} file(s) need locale mapping:",
                            ", ".join(report.unresolved_files[:3]),
                        ]
                    )
                )
            if report.failures:
                parts.append(f"{len(report.failures)} file(s) failed.")
            has_issues = bool(
                report.failures or report.unresolved_files or report.zero_segment_files
            )
            if has_issues:
                msg = QMessageBox(self)
                msg.setIcon(QMessageBox.Warning)
                msg.setWindowTitle("TM import sync")
                msg.setText(
                    " ".join(parts) if parts else "TM import sync finished with issues."
                )
                details = []
                if report.imported_files:
                    details.append(
                        "Imported:\n"
                        + "\n".join(f"- {name}" for name in report.imported_files)
                    )
                if report.unresolved_files:
                    details.append(
                        "Pending mapping:\n"
                        + "\n".join(f"- {name}" for name in report.unresolved_files)
                    )
                if report.zero_segment_files:
                    details.append(
                        "Imported with 0 segments:\n"
                        + "\n".join(f"- {name}" for name in report.zero_segment_files)
                    )
                if report.failures:
                    details.append("Failures:\n" + "\n".join(report.failures))
                msg.setDetailedText("\n\n".join(details))
                msg.exec()
            elif show_summary and report.imported_files:
                msg = QMessageBox(self)
                msg.setIcon(QMessageBox.Information)
                msg.setWindowTitle("TM import sync")
                msg.setText(" ".join(parts))
                msg.setDetailedText(
                    "Imported:\n"
                    + "\n".join(f"- {name}" for name in report.imported_files)
                )
                msg.exec()
            elif show_summary and not parts:
                msg = QMessageBox(self)
                msg.setIcon(QMessageBox.Information)
                msg.setWindowTitle("TM import sync")
                msg.setText("No TM files changed (already up to date).")
                if report.checked_files:
                    msg.setDetailedText(
                        "Checked:\n"
                        + "\n".join(f"- {name}" for name in report.checked_files)
                    )
                msg.exec()

    def _copy_tmx_to_import_dir(self, source: Path) -> Path:
        source = source.resolve()
        tm_dir = self._tm_import_dir_path()
        tm_dir.mkdir(parents=True, exist_ok=True)
        dest = tm_dir / source.name
        if source != dest:
            if dest.exists():
                i = 1
                while True:
                    candidate = tm_dir / f"{source.stem}_{i}{source.suffix}"
                    if not candidate.exists():
                        dest = candidate
                        break
                    i += 1
            shutil.copy2(source, dest)
        return dest.resolve()

    def _locale_for_path(self, path: Path) -> str | None:
        try:
            rel = path.relative_to(self._root)
        except ValueError:
            return None
        if not rel.parts:
            return None
        return rel.parts[0]

    def _locale_for_string_path(self, path_key: str) -> str | None:
        return self._locale_for_path(Path(path_key))

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
        try:
            dest = self._copy_tmx_to_import_dir(Path(path))
        except Exception as exc:
            QMessageBox.warning(self, "TMX import failed", str(exc))
            return
        self._sync_tm_import_folder(
            interactive=True,
            only_paths={dest},
            show_summary=True,
        )

    def _resolve_pending_tmx(self) -> None:
        self._sync_tm_import_folder(
            interactive=True,
            pending_only=True,
            show_summary=True,
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
        if not self._ensure_tm_store():
            QMessageBox.warning(self, "TM unavailable", "TM store is not available.")
            return
        locales = [loc for loc in self._selected_locales if loc != "EN"]
        if not locales:
            QMessageBox.information(self, "TM rebuild", "No locales selected.")
            return
        self._start_tm_rebuild(locales, interactive=True, force=True)

    def _show_copyable_report(self, title: str, text: str) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        dialog.resize(760, 460)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        editor = QPlainTextEdit(dialog)
        editor.setReadOnly(True)
        editor.setLineWrapMode(QPlainTextEdit.NoWrap)
        editor.setPlainText(text)
        layout.addWidget(editor)

        buttons = QDialogButtonBox(QDialogButtonBox.Close, dialog)
        copy_btn = buttons.addButton("Copy", QDialogButtonBox.ActionRole)
        copy_btn.clicked.connect(
            lambda: QGuiApplication.clipboard().setText(editor.toPlainText())
        )
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        dialog.exec()

    def _show_tm_diagnostics(self) -> None:
        if not self._ensure_tm_store():
            QMessageBox.warning(self, "TM unavailable", "TM store is not available.")
            return
        assert self._tm_store is not None
        policy = self._tm_query_policy()
        lookup = self._current_tm_lookup()
        report = self._tm_workflow.diagnostics_report_for_store(
            store=self._tm_store,
            policy=policy,
            lookup=lookup,
        )
        self._show_copyable_report("TM diagnostics", report)

    def _maybe_bootstrap_tm(self) -> None:
        if self._test_mode or not self._ensure_tm_store():
            return
        if not self._selected_locales:
            return
        locales = [loc for loc in self._selected_locales if loc != "EN"]
        if not locales:
            return
        self._start_tm_rebuild(locales, interactive=False, force=False)

    def _start_tm_rebuild(
        self, locales: Iterable[str], *, interactive: bool, force: bool
    ) -> None:
        if not self._tm_store:
            return
        if self._tm_rebuild_future is not None and not self._tm_rebuild_future.done():
            self.statusBar().showMessage("TM rebuild already running.", 3000)
            return
        locale_specs, en_encoding = self._tm_workflow.collect_rebuild_locales(
            locale_map=self._locales,
            selected_locales=list(locales),
        )
        if not locale_specs:
            if interactive:
                QMessageBox.information(self, "TM rebuild", "No TM entries found.")
            return
        if self._tm_rebuild_pool is None:
            self._tm_rebuild_pool = ThreadPoolExecutor(
                max_workers=1, thread_name_prefix="tzp-tm-rebuild"
            )
        self._tm_rebuild_locales = sorted({entry.locale for entry in locale_specs})
        self._tm_rebuild_interactive = interactive
        label = ", ".join(self._tm_rebuild_locales)
        prefix = "Rebuilding TM" if force else "Bootstrapping TM"
        self.statusBar().showMessage(f"{prefix} for {label}…", 0)
        self._tm_rebuild_future = self._tm_rebuild_pool.submit(
            self._tm_workflow.rebuild_project_tm,
            self._root,
            locale_specs,
            source_locale=self._tm_source_locale,
            en_encoding=en_encoding,
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

    def _finish_tm_rebuild(self, result: TMRebuildResult) -> None:
        self._tm_workflow.clear_cache()
        message = self._tm_workflow.format_rebuild_status(result)
        self.statusBar().showMessage(message, 8000)
        if self._left_stack.currentIndex() == 1:
            self._update_tm_suggestions()

    def _open_preferences(self) -> None:
        prefs = {
            "default_root": self._default_root,
            "tm_import_dir": self._tm_import_dir,
            "theme_mode": self._theme_mode,
            "prompt_write_on_exit": self._prompt_write_on_exit,
            "wrap_text": self._wrap_text_user,
            "large_text_optimizations": self._large_text_optimizations,
            "visual_highlight": self._visual_highlight,
            "visual_whitespace": self._visual_whitespace,
            "search_scope": self._search_scope,
            "replace_scope": self._replace_scope,
        }
        tm_files: list[dict[str, object]] = []
        if self._ensure_tm_store():
            with contextlib.suppress(Exception):
                tm_files = [
                    {
                        "tm_path": rec.tm_path,
                        "tm_name": rec.tm_name,
                        "source_locale": rec.source_locale,
                        "target_locale": rec.target_locale,
                        "source_locale_raw": rec.source_locale_raw,
                        "target_locale_raw": rec.target_locale_raw,
                        "segment_count": rec.segment_count,
                        "enabled": rec.enabled,
                        "status": rec.status,
                        "note": rec.note,
                    }
                    for rec in self._tm_store.list_import_files()
                ]
        dialog = PreferencesDialog(prefs, tm_files=tm_files, parent=self)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        self._apply_preferences(dialog.values())

    def _show_about(self) -> None:
        dialog = AboutDialog(self)
        dialog.exec()

    def _connect_system_theme_sync(self) -> None:
        if self._system_theme_sync_connected:
            return
        app = QApplication.instance()
        if app is None:
            return
        hints = app.styleHints()
        signal = getattr(hints, "colorSchemeChanged", None)
        if signal is None or not hasattr(signal, "connect"):
            return
        with contextlib.suppress(Exception):
            signal.connect(self._on_system_color_scheme_changed)
            self._system_theme_sync_connected = True

    def _disconnect_system_theme_sync(self) -> None:
        if not self._system_theme_sync_connected:
            return
        app = QApplication.instance()
        if app is None:
            self._system_theme_sync_connected = False
            return
        hints = app.styleHints()
        signal = getattr(hints, "colorSchemeChanged", None)
        if signal is not None and hasattr(signal, "disconnect"):
            with contextlib.suppress(Exception):
                signal.disconnect(self._on_system_color_scheme_changed)
        self._system_theme_sync_connected = False

    def _on_system_color_scheme_changed(self, *_args) -> None:
        if self._theme_mode != _THEME_SYSTEM:
            return
        self._apply_theme_mode(_THEME_SYSTEM, persist=False)

    def _apply_theme_mode(self, mode: object, *, persist: bool) -> None:
        normalized = _normalize_theme_mode(mode, default=_THEME_SYSTEM)
        app = QApplication.instance()
        if app is not None:
            normalized = _apply_app_theme(app, normalized)
        source_delegate = getattr(self, "_source_delegate", None)
        value_delegate = getattr(self, "_value_delegate", None)
        for delegate in (source_delegate, value_delegate):
            if delegate is None:
                continue
            clear_cache = getattr(delegate, "clear_visual_cache", None)
            if callable(clear_cache):
                clear_cache()
        self._theme_mode = normalized
        if normalized == _THEME_SYSTEM:
            self._prefs_extras.pop("UI_THEME_MODE", None)
        else:
            self._prefs_extras["UI_THEME_MODE"] = normalized
        if hasattr(self, "_detail_source") and hasattr(self, "_detail_translation"):
            self._apply_text_visual_options()
        table = getattr(self, "table", None)
        if table is not None and table.viewport():
            self.table.viewport().update()
        if persist:
            self._persist_preferences()

    def _apply_preferences(self, values: dict) -> None:
        theme_mode = _normalize_theme_mode(
            values.get("theme_mode", self._theme_mode), default=self._theme_mode
        )
        if theme_mode != self._theme_mode:
            self._apply_theme_mode(theme_mode, persist=False)
        self._prompt_write_on_exit = bool(values.get("prompt_write_on_exit", True))
        self._wrap_text_user = bool(values.get("wrap_text", False))
        large_text_opt = bool(
            values.get("large_text_optimizations", self._large_text_optimizations)
        )
        if large_text_opt != self._large_text_optimizations:
            self._large_text_optimizations = large_text_opt
            self._update_render_cost_flags()
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
        tm_import_dir = str(values.get("tm_import_dir", "")).strip()
        self._tm_import_dir = tm_import_dir or str(self._default_tm_import_dir())
        self._apply_tm_preferences_actions(values)
        search_scope = self._preferences_service.normalize_scope(
            values.get("search_scope", "FILE")
        )
        replace_scope = self._preferences_service.normalize_scope(
            values.get("replace_scope", "FILE")
        )
        if search_scope != self._search_scope:
            self._search_scope = search_scope
            if self.search_edit.text():
                self._schedule_search()
        self._replace_scope = replace_scope
        tm_resolve_pending = bool(values.get("tm_resolve_pending", False))
        tm_export_tmx = bool(values.get("tm_export_tmx", False))
        tm_rebuild = bool(values.get("tm_rebuild", False))
        tm_show_diagnostics = bool(values.get("tm_show_diagnostics", False))
        self._persist_preferences()
        if tm_resolve_pending:
            self._resolve_pending_tmx()
        if tm_export_tmx:
            self._export_tmx()
        if tm_rebuild:
            self._rebuild_tm_selected()
        if tm_show_diagnostics:
            self._show_tm_diagnostics()
        if self._left_stack.currentIndex() == 1:
            self._sync_tm_import_folder(interactive=True, show_summary=False)
            self._schedule_tm_update()
        self._update_replace_enabled()
        self._update_status_bar()

    def _apply_tm_preferences_actions(self, values: dict) -> None:
        actions = self._tm_workflow.build_preferences_actions(values)
        if actions.is_empty():
            return
        if not self._ensure_tm_store():
            return
        if actions.remove_paths and not self._confirm_tm_file_deletion(
            actions.remove_paths
        ):
            actions.remove_paths.clear()
        report = self._tm_workflow.apply_preferences_actions(
            store=self._tm_store,
            actions=actions,
            copy_to_import_dir=self._copy_tmx_to_import_dir,
        )
        if report.sync_paths:
            self._sync_tm_import_folder(
                interactive=True,
                only_paths=set(report.sync_paths),
                show_summary=True,
            )
        if report.failures:
            msg = QMessageBox(self)
            msg.setIcon(QMessageBox.Warning)
            msg.setWindowTitle("TM preferences")
            msg.setText("Some TM file operations failed.")
            msg.setDetailedText("\n".join(report.failures))
            msg.exec()

    def _confirm_tm_file_deletion(self, remove_paths: set[str]) -> bool:
        confirm = QMessageBox(self)
        confirm.setIcon(QMessageBox.Warning)
        confirm.setWindowTitle("Delete imported TM files")
        confirm.setText(
            "Selected TM files will be deleted from disk and removed from the TM store."
        )
        confirm.setInformativeText("This action cannot be undone.")
        confirm.setDetailedText("\n".join(sorted(remove_paths)))
        confirm.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel
        )
        confirm.setDefaultButton(QMessageBox.StandardButton.Cancel)
        return confirm.exec() == QMessageBox.StandardButton.Yes

    def _switch_locales(self) -> None:
        if not self._write_cache_current():
            return
        selectable = {k: v for k, v in self._locales.items() if k != "EN"}
        dialog = LocaleChooserDialog(
            selectable.values(), self, preselected=self._selected_locales
        )
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        plan = self._project_session_service.build_locale_switch_plan(
            requested_locales=dialog.selected_codes(),
            available_locales=self._locales.keys(),
            current_locales=self._selected_locales,
        )
        if plan is None or not plan.should_apply:
            return
        self._selected_locales = list(plan.selected_locales)
        if plan.reset_session_state:
            reset_plan = self._project_session_service.build_locale_reset_plan()
            self._apply_locale_reset_plan(reset_plan)
        tree_plan = self._project_session_service.build_tree_rebuild_plan(
            selected_locales=self._selected_locales,
            resize_splitter=True,
        )
        self._rebuild_tree_for_selected_locales(tree_plan=tree_plan)
        self._tm_bootstrap_pending = plan.tm_bootstrap_pending
        if plan.schedule_post_locale_tasks:
            self._schedule_post_locale_tasks()

    def _apply_locale_reset_plan(self, plan: _LocaleResetPlan) -> None:
        self._project_session_service.apply_locale_reset_plan(
            plan=plan,
            clear_files_by_locale=self._files_by_locale.clear,
            clear_opened_files=self._opened_files.clear,
            clear_conflict_files=self._conflict_files.clear,
            clear_conflict_sources=self._conflict_sources.clear,
            clear_conflict_notified=self._conflict_notified.clear,
            clear_current_file=lambda: setattr(self, "_current_pf", None),
            clear_current_model=lambda: setattr(self, "_current_model", None),
            clear_table_model=lambda: self.table.setModel(None),
            clear_status_combo=lambda: self._set_status_combo(None),
        )

    def _rebuild_tree_for_selected_locales(
        self, *, tree_plan: _TreeRebuildPlan
    ) -> None:
        self.fs_model = FsModel(
            self._root,
            [self._locales[c] for c in self._selected_locales],
            lazy=tree_plan.lazy_tree,
        )
        self.tree.setModel(self.fs_model)
        if tree_plan.preload_single_root:
            idx = self.fs_model.index(0, 0)
            if idx.isValid():
                self.fs_model.ensure_loaded_for_index(idx)
                self.tree.expand(idx)
        if tree_plan.expand_all:
            self.tree.expandAll()
        if not tree_plan.resize_splitter:
            return
        tree_width = self._initial_tree_width(tree_plan.lazy_tree)
        sizes = self._content_splitter.sizes()
        total = max(0, self._content_splitter.width())
        if total <= 0 and sizes:
            total = sum(sizes)
        if total > 0:
            self._content_splitter.setSizes([tree_width, max(100, total - tree_width)])

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
        with self._open_flow_guard():
            locale = self._locale_for_path(path)
            encoding = self._locales.get(
                locale, LocaleMeta("", Path(), "", "utf-8")
            ).charset
            callbacks = _OpenFileCallbacks(
                parse_eager=lambda file_path, enc: parse(file_path, encoding=enc),
                parse_lazy=lambda file_path, enc: parse_lazy(file_path, encoding=enc),
                read_cache=lambda file_path: _read_status_cache(self._root, file_path),
                touch_last_opened=lambda file_path, ts: _touch_last_opened(
                    self._root, file_path, ts
                ),
                now_ts=lambda: int(time.time()),
            )
            try:
                open_result = self._file_workflow_service.prepare_open_file(
                    path,
                    encoding,
                    use_lazy_parser=self._should_parse_lazy(path),
                    callbacks=callbacks,
                    hash_for_entry=lambda entry, cache_map: self._hash_for_cache(
                        entry, cache_map
                    ),
                )
            except Exception as exc:
                self._report_parse_error(path, exc)
                return
            pf = open_result.parsed_file

            self._current_encoding = encoding
            try:
                self._current_file_size = path.stat().st_size
            except OSError:
                self._current_file_size = 0

            source_lookup = self._load_en_source(
                path, locale, target_entries=pf.entries
            )
            self._cache_map = open_result.cache_map
            overlay = open_result.overlay
            changed_keys = overlay.changed_keys
            baseline_by_row = overlay.baseline_by_row
            conflict_originals = overlay.conflict_originals
            original_values = overlay.original_values
            self._current_pf = pf
            self._opened_files.add(path)
            if self._current_model:
                try:
                    self._current_model.dataChanged.disconnect(self._on_model_changed)
                    self._current_model.dataChanged.disconnect(
                        self._on_model_data_changed
                    )
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
            self._update_render_cost_flags()
            self._update_large_file_mode()
            self.table.selectionModel().currentChanged.connect(
                self._on_selection_changed
            )
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

            # (re)create undo/redo actions bound to this file's stack
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
            for action in (self.act_undo, self.act_redo):
                self.addAction(action)
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

    def _update_render_cost_flags(self) -> None:
        self._render_heavy = False
        if not self._current_model:
            return
        try:
            max_len = self._current_model.max_value_length()
        except Exception:
            max_len = 0
        decision = self._render_workflow_service.decide_render_cost(
            max_value_length=max_len,
            large_text_optimizations=self._large_text_optimizations,
            render_heavy_threshold=self._render_heavy_threshold,
            preview_limit=self._preview_limit,
        )
        self._render_heavy = decision.render_heavy
        self._current_model.set_preview_limit(decision.preview_limit)

    def _is_large_file(self) -> bool:
        return self._render_workflow_service.is_large_file(
            has_model=self._current_model is not None,
            row_count=self._current_model.rowCount() if self._current_model else 0,
            file_size=self._current_file_size,
            row_threshold=self._large_file_row_threshold,
            bytes_threshold=self._large_file_bytes_threshold,
            large_text_optimizations=self._large_text_optimizations,
            render_heavy=self._render_heavy,
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
        viewport = self.table.viewport()
        if viewport is None:
            return None
        first = self.table.rowAt(0)
        last = self.table.rowAt(max(0, viewport.height() - 1))
        return self._render_workflow_service.visible_row_span(
            total_rows=total,
            first_visible=first,
            last_visible=last,
            margin_pct=self._row_cache_margin_pct,
        )

    def _prefetch_visible_rows(self) -> None:
        if not self._current_model:
            return
        span = self._visible_row_span()
        prefetch = self._render_workflow_service.prefetch_span(
            span=span,
            total_rows=self._current_model.rowCount(),
            margin=self._lazy_row_prefetch_margin,
            large_file_mode=self._is_large_file(),
        )
        if not prefetch:
            return
        start, end = prefetch
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
        self._row_resize_cursor = None
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
        raw_span = self._pending_row_span or self._visible_row_span()
        span = self._render_workflow_service.resume_resize_span(
            span=raw_span,
            cursor=self._row_resize_cursor,
        )
        if span is None:
            return
        signature = self._row_height_cache_signature()
        if signature != self._row_height_cache_key:
            self._row_height_cache_key = signature
            self._row_height_cache.clear()
        start, end = span
        perf_trace = PERF_TRACE
        perf_start = perf_trace.start("row_resize")
        rows_processed = 0
        budget_ms = self._row_resize_budget_ms
        time_start = time.perf_counter()
        for row in range(start, end + 1):
            rows_processed += 1
            cached = self._row_height_cache.get(row)
            if cached is not None:
                if self.table.rowHeight(row) != cached:
                    self.table.setRowHeight(row, cached)
                if (time.perf_counter() - time_start) * 1000.0 >= budget_ms:
                    self._row_resize_cursor = row + 1
                    self._pending_row_span = span
                    self._row_resize_timer.start()
                    perf_trace.stop(
                        "row_resize", perf_start, items=rows_processed, unit="rows"
                    )
                    return
                continue
            height = self.table.sizeHintForRow(row)
            if height <= 0:
                continue
            self._row_height_cache[row] = height
            self.table.setRowHeight(row, height)
            if (time.perf_counter() - time_start) * 1000.0 >= budget_ms:
                self._row_resize_cursor = row + 1
                self._pending_row_span = span
                self._row_resize_timer.start()
                perf_trace.stop(
                    "row_resize", perf_start, items=rows_processed, unit="rows"
                )
                return
        self._pending_row_span = None
        self._row_resize_cursor = None
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
            self._sync_tm_import_folder(interactive=True, show_summary=False)
            if self._tm_bootstrap_pending:
                self._tm_bootstrap_pending = False
                self._maybe_bootstrap_tm()
            self._schedule_tm_update()
        if idx == 2:
            self._refresh_search_panel_results()

    def eventFilter(self, obj, event) -> bool:  # noqa: N802
        table = getattr(self, "table", None)
        if table is None:
            return super().eventFilter(obj, event)
        try:
            viewport = table.viewport()
        except RuntimeError:
            return super().eventFilter(obj, event)
        if obj is viewport:
            if event.type() == QEvent.MouseMove:
                idx = table.indexAt(event.pos())
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
        if not self._can_write_originals("save current file"):
            return False
        conflicts_resolved = bool(
            self._current_pf
            and self._current_model
            and self._ensure_conflicts_resolved(self._current_pf.path)
        )
        plan = self._file_workflow_service.build_save_current_run_plan(
            has_current_file=self._current_pf is not None,
            has_current_model=self._current_model is not None,
            conflicts_resolved=conflicts_resolved,
            has_changed_keys=bool(
                self._current_model and self._current_model.changed_keys()
            ),
        )
        if plan.immediate_result is not None:
            return plan.immediate_result
        if not plan.run_save:
            return False
        assert self._current_pf is not None
        assert self._current_model is not None
        changed = self._current_model.changed_values()
        callbacks = _SaveCurrentCallbacks(
            save_file=lambda pf, changed_values, enc: save(
                pf, changed_values, encoding=enc
            ),
            write_cache=lambda path, entries, last_opened: _write_status_cache(
                self._root,
                path,
                entries,
                changed_keys=set(),
                last_opened=last_opened,
            ),
            now_ts=lambda: int(time.time()),
        )
        try:
            self._file_workflow_service.persist_current_save(
                path=self._current_pf.path,
                parsed_file=self._current_pf,
                changed_values=changed,
                encoding=self._current_encoding,
                callbacks=callbacks,
            )
            self._current_model.reset_baseline()
            self.fs_model.set_dirty(self._current_pf.path, False)
            self._set_saved_status()
        except Exception as exc:
            QMessageBox.critical(self, "Save failed", str(exc))
            return False
        return True

    @contextlib.contextmanager
    def _open_flow_guard(self):
        self._open_flow_depth += 1
        try:
            yield
        finally:
            self._open_flow_depth = max(0, self._open_flow_depth - 1)

    def _can_write_originals(self, action: str) -> bool:
        if self._open_flow_depth <= 0:
            return True
        QMessageBox.warning(
            self,
            "Operation blocked",
            f"Cannot {action} while file open/read flow is active.",
        )
        return False

    def _request_write_original(self) -> None:
        if not self._can_write_originals("write original files"):
            return
        self._save_exit_flow_service.apply_write_original_flow(
            write_cache=self._write_cache_current,
            list_draft_files=self._draft_files,
            choose_action=self._show_save_files_dialog,
            save_all=self._save_all_files,
            notify_nothing_to_write=self._notify_nothing_to_write,
        )

    def _notify_nothing_to_write(self) -> None:
        QMessageBox.information(self, "Nothing to write", "No draft changes to write.")

    def _show_save_files_dialog(self, files: list[Path]) -> str:
        rel_files = list(
            self._save_exit_flow_service.build_save_dialog_labels(
                files,
                root=self._root,
            )
        )
        dialog = SaveFilesDialog(rel_files, self)
        dialog.exec()
        decision = dialog.choice()
        if decision != "write":
            return decision
        selected_rel: list[str] | None = None
        selected_files = getattr(dialog, "selected_files", None)
        if callable(selected_files):
            selected_rel = selected_files()
        files[:] = list(
            self._save_exit_flow_service.apply_save_dialog_selection(
                files=files,
                labels=rel_files,
                selected_labels=selected_rel,
            )
        )
        return decision

    def _draft_files(self) -> list[Path]:
        return self._project_session_service.collect_draft_files(
            root=self._root,
            locales=self._selected_locales,
        )

    def _all_draft_files(self, locales: Iterable[str] | None = None) -> list[Path]:
        return self._project_session_service.collect_draft_files(
            root=self._root,
            locales=locales,
        )

    def _mark_cached_dirty(self) -> None:
        perf_trace = PERF_TRACE
        perf_start = perf_trace.start("cache_scan")
        paths = self._all_draft_files(self._selected_locales)
        for path in paths:
            self.fs_model.set_dirty(path, True)
        perf_trace.stop("cache_scan", perf_start, items=len(paths), unit="files")

    def _schedule_post_locale_tasks(self) -> None:
        plan = self._project_session_service.build_post_locale_startup_plan(
            selected_locales=self._selected_locales
        )
        self._pending_post_locale_plan = plan
        if not plan.should_schedule:
            return
        if self._post_locale_timer.isActive():
            self._post_locale_timer.stop()
        self._post_locale_timer.start()

    def _run_post_locale_tasks(self) -> None:
        plan = self._pending_post_locale_plan
        self._pending_post_locale_plan = None
        if plan is None:
            plan = self._project_session_service.build_post_locale_startup_plan(
                selected_locales=self._selected_locales
            )
        if not plan.should_schedule:
            return
        perf_trace = PERF_TRACE
        perf_start = perf_trace.start("startup")
        executed = 0
        try:
            executed = self._project_session_service.run_post_locale_startup_tasks(
                plan=plan,
                run_cache_scan=self._mark_cached_dirty,
                run_auto_open=self._auto_open_last_file,
            )
        finally:
            perf_trace.stop("startup", perf_start, items=executed, unit="tasks")

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
        try:
            best_path, scanned = self._project_session_service.find_last_opened_file(
                root=self._root,
                selected_locales=self._selected_locales,
            )
            if not best_path:
                return
            index = self.fs_model.index_for_path(best_path)
            if index.isValid():
                self._file_chosen(index)
        finally:
            perf_trace.stop("auto_open", perf_start, items=scanned, unit="files")

    def _schedule_cache_migration(self) -> None:
        legacy_paths = _legacy_cache_paths(self._root)
        callbacks = _CacheMigrationScheduleCallbacks(
            migrate_all=lambda: _migrate_status_caches(self._root, self._locales),
            warn=lambda message: QMessageBox.warning(
                self,
                "Cache migration failed",
                message,
            ),
            start_timer=self._start_cache_migration_timer,
        )
        execution = self._project_session_service.execute_cache_migration_schedule(
            legacy_paths=legacy_paths,
            batch_size=self._migration_batch_size,
            migrated_count=self._migration_count,
            callbacks=callbacks,
        )
        self._pending_cache_migrations = list(execution.pending_paths)
        self._migration_count = execution.migrated_count

    def _run_cache_migration_batch(self) -> None:
        callbacks = _CacheMigrationBatchCallbacks(
            migrate_paths=lambda paths: _migrate_status_cache_paths(
                self._root,
                self._locales,
                list(paths),
            ),
            warn=lambda message: QMessageBox.warning(
                self,
                "Cache migration failed",
                message,
            ),
            stop_timer=self._stop_cache_migration_timer,
            show_status=lambda message: self.statusBar().showMessage(message, 5000),
        )
        execution = self._project_session_service.execute_cache_migration_batch(
            pending_paths=self._pending_cache_migrations,
            batch_size=self._migration_batch_size,
            migrated_count=self._migration_count,
            callbacks=callbacks,
        )
        self._pending_cache_migrations = list(execution.remaining_paths)
        self._migration_count = execution.migrated_count

    def _start_cache_migration_timer(self) -> None:
        if self._migration_timer is None:
            self._migration_timer = QTimer(self)
            self._migration_timer.timeout.connect(self._run_cache_migration_batch)
        if not self._migration_timer.isActive():
            self._migration_timer.start(0)

    def _stop_cache_migration_timer(self) -> None:
        if self._migration_timer is not None and self._migration_timer.isActive():
            self._migration_timer.stop()

    def _warn_orphan_caches(self) -> None:
        missing_by_locale = self._project_session_service.collect_orphan_cache_paths(
            root=self._root,
            selected_locales=self._selected_locales,
            warned_locales=self._orphan_cache_warned_locales,
        )
        for locale, missing in missing_by_locale.items():
            self._orphan_cache_warned_locales.add(locale)
            warning = self._project_session_service.build_orphan_cache_warning(
                locale=locale,
                orphan_paths=missing,
                root=self._root,
                preview_limit=20,
            )
            msg = QMessageBox(self)
            msg.setIcon(QMessageBox.Warning)
            msg.setWindowTitle(warning.window_title)
            msg.setText(warning.text)
            msg.setInformativeText(warning.informative_text)
            msg.setDetailedText(warning.detailed_text)
            purge = msg.addButton("Purge", QMessageBox.AcceptRole)
            msg.addButton("Dismiss", QMessageBox.RejectRole)
            msg.exec()
            if msg.clickedButton() is purge:
                for path in warning.orphan_paths:
                    try:
                        path.unlink()
                    except OSError:
                        continue

    def _save_all_files(self, files: list[Path]) -> None:
        if not self._can_write_originals("write original files"):
            return
        outcome = self._save_exit_flow_service.run_save_batch_flow(
            files=files,
            current_file=self._current_pf.path if self._current_pf else None,
            save_current=self._save_current,
            save_from_cache=self._save_file_from_cache,
        )
        plan = self._save_exit_flow_service.build_save_batch_render_plan(
            outcome=outcome,
            root=self._root,
        )
        if plan.aborted:
            return
        if plan.warning_message:
            QMessageBox.warning(
                self,
                "Save incomplete",
                f"Some files could not be written:\n{plan.warning_message}",
            )
        elif plan.set_saved_status:
            self._set_saved_status()

    def _save_file_from_cache(self, path: Path) -> bool:
        if not self._can_write_originals(f"write {path.name}"):
            return False
        if not self._ensure_conflicts_resolved(path):
            return False
        cached = _read_status_cache(self._root, path)
        locale = self._locale_for_path(path)
        encoding = self._locales.get(
            locale, LocaleMeta("", Path(), "", "utf-8")
        ).charset
        callbacks = _SaveFromCacheCallbacks(
            parse_file=lambda file_path, enc: parse(file_path, encoding=enc),
            save_file=lambda pf, changed_values, enc: save(
                pf, changed_values, encoding=enc
            ),
            write_cache=lambda file_path, entries: _write_status_cache(
                self._root,
                file_path,
                entries,
                changed_keys=set(),
            ),
        )
        try:
            result = self._file_workflow_service.write_from_cache(
                path,
                encoding,
                cache_map=cached,
                callbacks=callbacks,
                hash_for_entry=lambda entry: self._hash_for_cache(
                    entry,
                    cached,
                ),
            )
        except _SaveFromCacheParseError as exc:
            self._report_parse_error(path, exc.original)
            return False
        except Exception as exc:
            QMessageBox.warning(self, "Save failed", str(exc))
            return False
        if not result.had_drafts:
            return True
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
        self._tm_workflow.queue_updates(str(path), rows)
        if self._tm_flush_timer.isActive():
            self._tm_flush_timer.stop()
        self._tm_flush_timer.start()

    def _flush_tm_updates(self, *, paths: Iterable[Path] | None = None) -> None:
        if not self._tm_store:
            return
        wanted = None if paths is None else [str(path) for path in paths]
        batches = self._tm_workflow.pending_batches(
            locale_for_path=self._locale_for_string_path,
            paths=wanted,
        )
        for batch in batches:
            try:
                self._tm_store.upsert_project_entries(
                    batch.rows,
                    source_locale=self._tm_source_locale,
                    target_locale=batch.target_locale,
                    file_path=batch.file_key,
                )
            except Exception as exc:
                QMessageBox.warning(self, "TM update failed", str(exc))
                continue
            self._tm_workflow.mark_batch_flushed(batch.file_key)

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
        self._set_search_panel_message(
            "Press Enter in the search box to populate results."
        )

    def _update_case_toggle_ui(self) -> None:
        if not hasattr(self, "search_case_btn") or self.search_case_btn is None:
            return
        if self._search_case_sensitive:
            self.search_case_btn.setToolTip(
                "Case-sensitive search (click to ignore case)"
            )
        else:
            self.search_case_btn.setToolTip(
                "Case-insensitive search (click to match case)"
            )

    def _toggle_search_case_sensitive(self, checked: bool) -> None:
        self._search_case_sensitive = bool(checked)
        self._prefs_extras["SEARCH_CASE_SENSITIVE"] = (
            "true" if self._search_case_sensitive else "false"
        )
        self._update_case_toggle_ui()
        self._on_search_controls_changed()
        self._persist_preferences()

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

    def _prepare_replace_request(self) -> _ReplaceRequest | None:
        query = self.search_edit.text()
        replacement = self.replace_edit.text()
        use_regex = self.regex_check.isChecked()
        try:
            return self._search_replace_service.build_replace_request(
                query=query,
                replacement=replacement,
                use_regex=use_regex,
                case_sensitive=self._search_case_sensitive,
            )
        except _ReplaceRequestError:
            QMessageBox.warning(self, "Invalid regex", "Regex pattern is invalid.")
            return None

    def _files_for_scope(self, scope: str) -> list[Path]:
        current_path = self._current_pf.path if self._current_pf else None
        current_locale = (
            self._locale_for_path(current_path) if current_path is not None else None
        )
        return self._search_replace_service.scope_files(
            scope=scope,
            current_file=current_path,
            current_locale=current_locale,
            selected_locales=self._selected_locales,
            files_for_locale=self._files_for_locale,
        )

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
        request = self._prepare_replace_request()
        if request is None:
            return
        current = self.table.currentIndex()
        if not current.isValid():
            return
        model = self._current_model
        row = current.row()
        callbacks = _ReplaceCurrentRowCallbacks(
            read_text=lambda row_idx: model.index(row_idx, 2).data(Qt.EditRole),
            write_text=lambda row_idx, text: model.setData(
                model.index(row_idx, 2), text, Qt.EditRole
            ),
        )
        try:
            changed = self._search_replace_service.apply_replace_in_row(
                row=row,
                request=request,
                callbacks=callbacks,
            )
        except re.error as exc:
            QMessageBox.warning(self, "Replace failed", str(exc))
            return
        if changed:
            self._schedule_search()

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
        model = self._current_model
        callbacks = _ReplaceAllRowsCallbacks(
            row_count=model.rowCount,
            read_text=lambda row: model.index(row, 2).data(Qt.EditRole),
            write_text=lambda _row, _text: None,
        )
        try:
            return self._search_replace_service.count_replace_all_in_rows(
                pattern=pattern,
                replacement=replacement,
                use_regex=use_regex,
                matches_empty=matches_empty,
                has_group_ref=has_group_ref,
                callbacks=callbacks,
            )
        except re.error as exc:
            QMessageBox.warning(self, "Replace failed", str(exc))
            return None

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
        callbacks = _ReplaceAllFileCountCallbacks(
            parse_file=lambda file_path: parse(file_path, encoding=encoding),
            read_cache=lambda file_path: _read_status_cache(self._root, file_path),
        )
        try:
            return self._search_replace_service.count_replace_all_in_file(
                path,
                pattern=pattern,
                replacement=replacement,
                use_regex=use_regex,
                matches_empty=matches_empty,
                has_group_ref=has_group_ref,
                callbacks=callbacks,
                hash_for_entry=lambda entry, cache_map: self._hash_for_cache(
                    entry, cache_map
                ),
            )
        except _ReplaceAllFileParseError as exc:
            self._report_parse_error(exc.path, exc.original)
            return None
        except re.error as exc:
            QMessageBox.warning(self, "Replace failed", str(exc))
            return None

    def _replace_all(self) -> None:
        if not self._current_model:
            return
        request = self._prepare_replace_request()
        if request is None:
            return
        scope = self._replace_scope
        files = self._files_for_scope(scope)
        if not files:
            return
        current_path = self._current_pf.path if self._current_pf else None
        locale = (
            self._locale_for_path(current_path) if current_path is not None else None
        )

        def _display_name(path: Path) -> str:
            with contextlib.suppress(ValueError):
                return str(path.relative_to(self._root))
            return str(path)

        run_plan = self._search_replace_service.build_replace_all_run_plan(
            scope=scope,
            current_locale=locale,
            selected_locale_count=len(self._selected_locales),
            files=files,
            current_file=current_path,
            display_name=_display_name,
            count_in_current=lambda: self._replace_all_count_in_model(
                request.pattern,
                request.replacement,
                request.use_regex,
                request.matches_empty,
                request.has_group_ref,
            ),
            count_in_file=lambda path: self._replace_all_count_in_file(
                path,
                request.pattern,
                request.replacement,
                request.use_regex,
                request.matches_empty,
                request.has_group_ref,
            ),
        )
        if run_plan is None:
            return
        if not run_plan.run_replace:
            return
        if run_plan.show_confirmation:
            dialog = ReplaceFilesDialog(
                list(run_plan.counts), run_plan.scope_label, self
            )
            dialog.exec()
            if not dialog.confirmed():
                return
        applied = self._search_replace_service.apply_replace_all(
            files=files,
            current_file=current_path,
            apply_in_current=lambda: self._replace_all_in_model(
                request.pattern,
                request.replacement,
                request.use_regex,
                request.matches_empty,
                request.has_group_ref,
            ),
            apply_in_file=lambda path: self._replace_all_in_file(
                path,
                request.pattern,
                request.replacement,
                request.use_regex,
                request.matches_empty,
                request.has_group_ref,
            ),
        )
        if not applied:
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
        model = self._current_model
        callbacks = _ReplaceAllRowsCallbacks(
            row_count=model.rowCount,
            read_text=lambda row: model.index(row, 2).data(Qt.EditRole),
            write_text=lambda row, text: model.setData(
                model.index(row, 2), text, Qt.EditRole
            ),
        )
        try:
            self._search_replace_service.apply_replace_all_in_rows(
                pattern=pattern,
                replacement=replacement,
                use_regex=use_regex,
                matches_empty=matches_empty,
                has_group_ref=has_group_ref,
                callbacks=callbacks,
            )
        except re.error as exc:
            QMessageBox.warning(self, "Replace failed", str(exc))
            return False
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
        callbacks = _ReplaceAllFileApplyCallbacks(
            parse_file=lambda file_path: parse(file_path, encoding=encoding),
            read_cache=lambda file_path: _read_status_cache(self._root, file_path),
            write_cache=lambda file_path, entries, changed_keys, original_values: (
                _write_status_cache(
                    self._root,
                    file_path,
                    entries,
                    changed_keys=changed_keys,
                    original_values=dict(original_values),
                    force_original=set(original_values),
                )
            ),
        )
        try:
            result = self._search_replace_service.apply_replace_all_in_file(
                path,
                pattern=pattern,
                replacement=replacement,
                use_regex=use_regex,
                matches_empty=matches_empty,
                has_group_ref=has_group_ref,
                callbacks=callbacks,
                hash_for_entry=lambda entry, cache_map: self._hash_for_cache(
                    entry, cache_map
                ),
            )
        except _ReplaceAllFileParseError as exc:
            self._report_parse_error(exc.path, exc.original)
            return False
        except re.error as exc:
            QMessageBox.warning(self, "Replace failed", str(exc))
            return False
        if result.changed_any:
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
        prompt_plan = self._conflict_workflow_service.build_prompt_plan(
            has_conflicts=self._has_conflicts(path),
            is_current_file=bool(self._current_pf and self._current_pf.path == path),
            for_save=for_save,
        )
        if prompt_plan.immediate_result is not None:
            return prompt_plan.immediate_result
        assert prompt_plan.require_dialog
        rel = str(path.relative_to(self._root))
        dialog = ConflictChoiceDialog(rel, len(self._conflict_files[path]), self)
        dialog.exec()
        return self._conflict_workflow_service.execute_choice(
            dialog.choice(),
            on_drop_cache=lambda: self._resolve_conflicts_drop_cache(path),
            on_drop_original=lambda: self._resolve_conflicts_drop_original(path),
            on_merge=lambda: self._resolve_conflicts_merge(path),
        )

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
        plan = self._conflict_workflow_service.build_resolution_run_plan(
            action="drop_cache",
            has_current_file=self._current_pf is not None,
            has_current_model=self._current_model is not None,
            is_current_file=bool(self._current_pf and self._current_pf.path == path),
            conflict_count=len(self._conflict_files.get(path, {})),
        )
        if plan.immediate_result is not None:
            return plan.immediate_result
        if not plan.run_resolution:
            return False
        assert self._current_model is not None
        resolution = self._conflict_workflow_service.resolve_drop_cache(
            changed_keys=self._current_model.changed_keys(),
            baseline_values=self._current_model.baseline_values(),
            conflict_originals=self._conflict_files.get(path, {}),
        )
        return self._persist_conflict_resolution(path, resolution)

    def _resolve_conflicts_drop_original(self, path: Path) -> bool:
        plan = self._conflict_workflow_service.build_resolution_run_plan(
            action="drop_original",
            has_current_file=self._current_pf is not None,
            has_current_model=self._current_model is not None,
            is_current_file=bool(self._current_pf and self._current_pf.path == path),
            conflict_count=len(self._conflict_files.get(path, {})),
        )
        if plan.immediate_result is not None:
            return plan.immediate_result
        if not plan.run_resolution:
            return False
        assert self._current_model is not None
        resolution = self._conflict_workflow_service.resolve_drop_original(
            changed_keys=self._current_model.changed_keys(),
            baseline_values=self._current_model.baseline_values(),
            conflict_originals=self._conflict_files.get(path, {}),
        )
        return self._persist_conflict_resolution(path, resolution)

    def _persist_conflict_resolution(
        self,
        path: Path,
        resolution: _ConflictResolution,
    ) -> bool:
        if not self._current_pf:
            return False
        return self._conflict_workflow_service.execute_persist_resolution(
            resolution=resolution,
            callbacks=_ConflictPersistCallbacks(
                write_cache=lambda plan: _write_status_cache(
                    self._root,
                    path,
                    self._current_pf.entries,
                    changed_keys=set(plan.changed_keys),
                    original_values=plan.original_values,
                    force_original=set(plan.force_original),
                ),
                mark_file_clean=lambda: self.fs_model.set_dirty(path, False),
                clear_conflicts=lambda: self._clear_conflicts(path),
                reload_current_file=lambda: self._reload_file(path),
            ),
        )

    def _resolve_conflicts_merge(self, path: Path) -> bool:
        plan = self._conflict_workflow_service.build_resolution_run_plan(
            action="merge",
            has_current_file=self._current_pf is not None,
            has_current_model=self._current_model is not None,
            is_current_file=bool(self._current_pf and self._current_pf.path == path),
            conflict_count=len(self._conflict_files.get(path, {})),
        )
        if plan.immediate_result is not None:
            return plan.immediate_result
        if not plan.run_resolution:
            return False
        assert self._current_pf is not None
        assert self._current_model is not None
        conflict_originals = self._conflict_files.get(path, {})
        sources = self._conflict_sources.get(path, {})
        execution = self._conflict_workflow_service.execute_merge_resolution(
            entries=self._current_pf.entries,
            changed_keys=self._current_model.changed_keys(),
            baseline_values=self._current_model.baseline_values(),
            conflict_originals=conflict_originals,
            sources=sources,
            request_resolutions=lambda rows: self._run_merge_ui(path, rows),
        )
        if execution.immediate_result is not None:
            return execution.immediate_result
        if not execution.resolved or execution.resolution is None:
            return False
        return self._persist_conflict_resolution(path, execution.resolution)

    def _run_merge_ui(
        self, path: Path, rows: list[_ConflictMergeRow]
    ) -> dict[str, tuple[str, Literal["original", "cache"]]] | None:
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

    def _build_merge_view(self, path: Path, rows: list[_ConflictMergeRow]) -> None:
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

        for row_data in rows:
            key = row_data.key
            source = row_data.source_value
            original = row_data.original_value
            cache = row_data.cache_value
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
        out: dict[str, tuple[str, Literal["original", "cache"]]] = {}
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
        result = self._search_replace_service.load_search_rows_from_file(
            path=path,
            encoding=encoding,
            use_lazy_parser=self._should_parse_lazy(path),
            include_source=include_source,
            include_value=include_value,
            cache_row_limit=self._search_cache_row_limit,
            callbacks=_SearchRowsFileCallbacks(
                parse_eager=lambda file_path, enc: parse(file_path, encoding=enc),
                parse_lazy=lambda file_path, enc: parse_lazy(file_path, encoding=enc),
                read_cache=lambda file_path: _read_status_cache(self._root, file_path),
                load_source_lookup=lambda parsed_file: (
                    self._source_lookup_for_rows(
                        path=path,
                        locale=locale,
                        entries=parsed_file.entries,
                    )
                ),
            ),
            hash_for_entry=lambda entry, cache_map: self._hash_for_cache(
                entry, cache_map
            ),
        )
        if result is None:
            return (), 0
        return result.rows, result.entry_count

    def _source_lookup_for_rows(
        self,
        *,
        path: Path,
        locale: str,
        entries: Sequence[Entry],
    ) -> tuple[Sequence[str] | None, Callable[[str], str]]:
        source_lookup = self._load_en_source(path, locale, target_entries=entries)
        return source_lookup.by_row, lambda key: source_lookup.get(key, "")

    def _cached_rows_from_file(
        self,
        path: Path,
        locale: str,
        *,
        include_source: bool,
        include_value: bool,
    ) -> Iterable[_SearchRow]:
        stamp = self._search_replace_service.collect_rows_cache_stamp(
            path=path,
            include_source=include_source,
            include_value=include_value,
            callbacks=_SearchRowsCacheStampCallbacks(
                file_mtime_ns=self._file_mtime_for_rows,
                cache_mtime_ns=self._cache_mtime_for_rows,
                source_mtime_ns=lambda file_path: self._source_mtime_for_rows(
                    file_path, locale
                ),
            ),
        )
        if stamp is None:
            return []
        key = (path, include_source, include_value)
        cached = self._search_rows_cache.get(key)
        lookup_plan = self._search_replace_service.build_rows_cache_lookup_plan(
            path=path,
            include_source=include_source,
            include_value=include_value,
            file_mtime_ns=stamp.file_mtime_ns,
            cache_mtime_ns=stamp.cache_mtime_ns,
            source_mtime_ns=stamp.source_mtime_ns,
            cached_stamp=cached[0] if cached else None,
        )
        cache_key = (
            lookup_plan.key.path,
            lookup_plan.key.include_source,
            lookup_plan.key.include_value,
        )
        if lookup_plan.use_cached_rows and cached:
            self._search_rows_cache.move_to_end(cache_key)
            return cached[1]
        rows, entry_count = self._rows_from_file(
            path,
            locale,
            include_source=include_source,
            include_value=include_value,
        )
        store_plan = self._search_replace_service.build_rows_cache_store_plan(
            rows_materialized=isinstance(rows, list),
            entry_count=entry_count,
            cache_row_limit=self._search_cache_row_limit,
        )
        if store_plan.should_store_rows and isinstance(rows, list):
            self._search_rows_cache[cache_key] = (lookup_plan.stamp, rows)
            self._search_rows_cache.move_to_end(cache_key)
            if len(self._search_rows_cache) > self._search_cache_max:
                self._search_rows_cache.popitem(last=False)
        return rows

    def _file_mtime_for_rows(self, path: Path) -> int | None:
        try:
            return path.stat().st_mtime_ns
        except OSError:
            return None

    def _cache_mtime_for_rows(self, path: Path) -> int:
        try:
            rel = path.relative_to(self._root)
        except ValueError:
            return 0
        cache_path = (self._root / self._app_config.cache_dir / rel).with_suffix(
            self._app_config.cache_ext
        )
        with contextlib.suppress(OSError):
            return cache_path.stat().st_mtime_ns
        return 0

    def _source_mtime_for_rows(self, path: Path, locale: str) -> int:
        en_path = self._en_path_for(path, locale)
        if not en_path:
            return 0
        with contextlib.suppress(OSError):
            return en_path.stat().st_mtime_ns
        return 0

    def _search_files_for_scope(self) -> list[Path]:
        return list(self._files_for_scope(self._search_scope))

    def _find_match_in_rows(
        self,
        rows: Iterable[_SearchRow],
        query: str,
        field: _SearchField,
        use_regex: bool,
        *,
        start_row: int,
        direction: int,
        case_sensitive: bool,
    ) -> _SearchMatch | None:
        return self._search_replace_service.find_match_in_rows(
            rows,
            query,
            field,
            use_regex,
            start_row=start_row,
            direction=direction,
            case_sensitive=case_sensitive,
        )

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
        rows = self._search_rows_for_file(
            path,
            include_source=include_source,
            include_value=include_value,
        )
        return self._find_match_in_rows(
            rows,
            query,
            field,
            use_regex,
            start_row=start_row,
            direction=direction,
            case_sensitive=self._search_case_sensitive,
        )

    def _search_rows_for_file(
        self,
        path: Path,
        *,
        include_source: bool,
        include_value: bool,
    ) -> Iterable[_SearchRow]:
        locale = self._locale_for_path(path)
        is_current = bool(self._current_pf and path == self._current_pf.path)
        plan = self._search_replace_service.build_rows_source_plan(
            locale_known=bool(locale),
            is_current_file=is_current,
            has_current_model=bool(self._current_model),
        )
        if not plan.has_rows:
            return ()
        if plan.use_active_model_rows:
            return self._rows_from_model(
                include_source=include_source,
                include_value=include_value,
            )
        assert locale is not None
        return self._cached_rows_from_file(
            path,
            locale,
            include_source=include_source,
            include_value=include_value,
        )

    def _select_match(self, match: _SearchMatch) -> bool:
        open_plan = self._search_replace_service.build_match_open_plan(
            has_match=bool(match),
            match_file=(match.file if match else None),
            current_file=(self._current_pf.path if self._current_pf else None),
        )
        if open_plan.open_target_file and open_plan.target_file is not None:
            index = self.fs_model.index_for_path(open_plan.target_file)
            if not index.isValid():
                return False
            self._file_chosen(index)
            if self._current_pf and self._current_pf.path == open_plan.target_file:
                self.tree.selectionModel().setCurrentIndex(
                    index,
                    QItemSelectionModel.ClearAndSelect | QItemSelectionModel.Rows,
                )
                self.tree.scrollTo(index, QAbstractItemView.PositionAtCenter)
        apply_plan = self._search_replace_service.build_match_apply_plan(
            has_match=bool(match),
            match_file=(match.file if match else None),
            current_file=(self._current_pf.path if self._current_pf else None),
            has_current_model=bool(self._current_model),
            match_row=(match.row if match else -1),
            row_count=(self._current_model.rowCount() if self._current_model else 0),
            column=self._search_column,
        )
        if not apply_plan.select_in_table:
            return False
        assert self._current_model is not None
        model_index = self._current_model.index(
            apply_plan.target_row, apply_plan.target_column
        )
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
        self._search_progress_text = ""
        self._update_status_bar()
        column = int(self.search_mode.currentData())
        self._search_column = column
        files = self._search_files_for_scope()
        current_row = None if anchor_row is None else anchor_row
        if current_row is None:
            current = self.table.currentIndex()
            if current.isValid():
                current_row = current.row()
        plan = self._search_replace_service.build_search_run_plan(
            query_text=self.search_edit.text(),
            column=column,
            use_regex=bool(self.regex_check.isChecked()),
            files=files,
            current_file=(
                anchor_path
                if anchor_path is not None
                else (self._current_pf.path if self._current_pf else None)
            ),
            current_row=current_row,
            direction=direction,
        )
        if not plan.run_search:
            if plan.status_message:
                self._set_search_panel_message(plan.status_message)
            return False
        assert plan.field is not None
        self._refresh_search_panel_results(
            query=plan.query,
            use_regex=plan.use_regex,
            field=plan.field,
            include_source=plan.include_source,
            include_value=plan.include_value,
            files=list(plan.files),
        )

        def _find_in_file(path: Path, start_row: int) -> _SearchMatch | None:
            return self._find_match_in_file(
                path,
                query=plan.query,
                field=plan.field,
                use_regex=plan.use_regex,
                include_source=plan.include_source,
                include_value=plan.include_value,
                start_row=start_row,
                direction=direction,
            )

        match = self._search_replace_service.search_across_files(
            files=list(plan.files),
            anchor_path=plan.anchor_path,
            anchor_row=plan.anchor_row,
            direction=direction,
            wrap=wrap,
            find_in_file=_find_in_file,
        )
        return bool(match and self._select_match(match))

    def _set_search_panel_message(self, text: str) -> None:
        if (
            hasattr(self, "_search_status_label")
            and self._search_status_label is not None
        ):
            self._search_status_label.setText(text)
        if (
            hasattr(self, "_search_results_list")
            and self._search_results_list is not None
        ):
            self._search_results_list.clear()

    def _refresh_search_panel_results(
        self,
        *,
        query: str | None = None,
        use_regex: bool | None = None,
        field: _SearchField | None = None,
        include_source: bool | None = None,
        include_value: bool | None = None,
        files: list[Path] | None = None,
    ) -> None:
        if (
            not hasattr(self, "_search_results_list")
            or self._search_results_list is None
        ):
            return
        query_text = (query if query is not None else self.search_edit.text()).strip()
        if not query_text:
            self._set_search_panel_message(
                "Press Enter in the search box to populate results."
            )
            return
        if use_regex is None:
            use_regex = bool(self.regex_check.isChecked())
        if field is None or include_source is None or include_value is None:
            column = int(self.search_mode.currentData())
            field, include_source, include_value = (
                self._search_replace_service.search_spec_for_column(column)
            )
        if files is None:
            files = self._search_files_for_scope()
        if not files:
            self._set_search_panel_message("No files in current search scope.")
            return

        def _iter_matches_for_file(path: Path) -> Iterable[_SearchMatch]:
            rows = self._search_rows_for_file(
                path,
                include_source=include_source,
                include_value=include_value,
            )
            return _iter_search_matches(
                rows,
                query_text,
                field,
                use_regex,
                case_sensitive=self._search_case_sensitive,
                include_preview=True,
                preview_chars=96,
            )

        plan = self._search_replace_service.build_search_panel_plan(
            files=files,
            root=self._root,
            result_limit=self._search_panel_result_limit,
            iter_matches_for_file=_iter_matches_for_file,
        )
        self._search_results_list.clear()
        for row in plan.items:
            item = QListWidgetItem(row.label)
            item.setData(Qt.UserRole, (str(row.file), int(row.row)))
            self._search_results_list.addItem(item)
        self._search_status_label.setText(plan.status_message)

    def _open_search_result_item(self, item: QListWidgetItem) -> None:
        payload = item.data(Qt.UserRole)
        if not isinstance(payload, tuple) or len(payload) != 2:
            return
        raw_path, raw_row = payload
        try:
            match = _SearchMatch(Path(str(raw_path)), int(raw_row))
        except Exception:
            return
        self._select_match(match)

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
                        self._current_model.index(row, col).data(
                            Qt.EditRole if col in (1, 2) else Qt.DisplayRole
                        )
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
        text = (
            idx.data(Qt.EditRole)
            if idx.column() in (1, 2)
            else idx.data(Qt.DisplayRole)
        )
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
        effective = self._wrap_text_user
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
                self.act_wrap.setToolTip("Wrap enabled; large-file mode active")
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
        self._preferences_service.persist_main_window_preferences(
            prompt_write_on_exit=self._prompt_write_on_exit,
            wrap_text=self._wrap_text_user,
            large_text_optimizations=self._large_text_optimizations,
            last_root=str(self._root),
            last_locales=list(self._selected_locales),
            window_geometry=geometry,
            default_root=self._default_root,
            tm_import_dir=self._tm_import_dir,
            search_scope=self._search_scope,
            replace_scope=self._replace_scope,
            extras=dict(self._prefs_extras),
        )

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
        plan = self._tm_workflow.build_update_plan(
            has_store=self._tm_store is not None,
            panel_index=self._left_stack.currentIndex(),
            timer_active=self._tm_update_timer.isActive(),
            tm_panel_index=1,
        )
        if not plan.run_update:
            return
        if plan.stop_timer:
            self._tm_update_timer.stop()
        if plan.start_timer:
            self._tm_update_timer.start()

    def _update_tm_apply_state(self) -> None:
        items = self._tm_list.selectedItems()
        match = items[0].data(Qt.UserRole) if items else None
        plan = self._tm_workflow.build_selection_plan(
            match=match if isinstance(match, TMMatch) else None,
            lookup=self._current_tm_lookup(),
        )
        self._tm_apply_btn.setEnabled(plan.apply_enabled)
        self._set_tm_preview(plan)

    def _set_tm_preview(self, plan: _TMSelectionPlan) -> None:
        if not plan.apply_enabled:
            self._tm_source_preview.clear()
            self._tm_target_preview.clear()
            self._tm_source_preview.setExtraSelections([])
            self._tm_target_preview.setExtraSelections([])
            return
        self._tm_source_preview.setPlainText(plan.source_preview)
        self._tm_target_preview.setPlainText(plan.target_preview)
        terms = list(plan.query_terms)
        with contextlib.suppress(Exception):
            self._highlight_tm_preview(self._tm_source_preview, terms)
            self._highlight_tm_preview(self._tm_target_preview, terms)

    def _highlight_tm_preview(self, editor: QPlainTextEdit, terms: list[str]) -> None:
        if not terms:
            editor.setExtraSelections([])
            return
        fmt = QTextCharFormat()
        fmt.setBackground(QColor(255, 235, 120, 170))
        fmt.setForeground(QColor(0, 0, 0))
        selections: list[QTextEdit.ExtraSelection] = []
        doc = editor.document()
        max_hits = 200
        for term in terms:
            pattern = QRegularExpression(re.escape(term))
            pattern.setPatternOptions(QRegularExpression.CaseInsensitiveOption)
            pos = 0
            while True:
                cursor = doc.find(pattern, pos)
                if cursor.isNull():
                    break
                sel = QTextEdit.ExtraSelection()
                sel.cursor = cursor
                sel.format = fmt
                selections.append(sel)
                if len(selections) >= max_hits:
                    editor.setExtraSelections(selections)
                    return
                next_pos = cursor.selectionEnd()
                if next_pos <= pos:
                    next_pos = pos + 1
                pos = next_pos
        editor.setExtraSelections(selections)

    def _tm_query_policy(self) -> TMQueryPolicy:
        return self._tm_workflow.build_filter_plan(
            source_locale=self._tm_source_locale,
            min_score=self._tm_min_score,
            origin_project=self._tm_origin_project,
            origin_import=self._tm_origin_import,
        ).policy

    def _tm_apply_filter_plan(self, plan) -> None:
        self._tm_min_score = plan.policy.min_score
        self._tm_origin_project = plan.policy.origin_project
        self._tm_origin_import = plan.policy.origin_import
        self._prefs_extras.update(plan.prefs_extras)
        if self._tm_score_spin.value() != self._tm_min_score:
            self._tm_score_spin.blockSignals(True)
            try:
                self._tm_score_spin.setValue(self._tm_min_score)
            finally:
                self._tm_score_spin.blockSignals(False)
        if self._tm_origin_project_cb.isChecked() != self._tm_origin_project:
            self._tm_origin_project_cb.blockSignals(True)
            try:
                self._tm_origin_project_cb.setChecked(self._tm_origin_project)
            finally:
                self._tm_origin_project_cb.blockSignals(False)
        if self._tm_origin_import_cb.isChecked() != self._tm_origin_import:
            self._tm_origin_import_cb.blockSignals(True)
            try:
                self._tm_origin_import_cb.setChecked(self._tm_origin_import)
            finally:
                self._tm_origin_import_cb.blockSignals(False)

    def _on_tm_filters_changed(self) -> None:
        plan = self._tm_workflow.build_filter_plan(
            source_locale=self._tm_source_locale,
            min_score=int(self._tm_score_spin.value()),
            origin_project=bool(self._tm_origin_project_cb.isChecked()),
            origin_import=bool(self._tm_origin_import_cb.isChecked()),
        )
        self._tm_apply_filter_plan(plan)
        self._persist_preferences()
        self._update_tm_suggestions()

    def _current_tm_lookup(self) -> tuple[str, str] | None:
        if not (self._current_model and self._current_pf):
            return None
        current = self.table.currentIndex()
        if not current.isValid():
            return None
        source_index = self._current_model.index(current.row(), 1)
        source_text = str(source_index.data(Qt.EditRole) or "")
        locale = self._locale_for_path(self._current_pf.path)
        return self._tm_workflow.build_lookup(
            source_text=source_text,
            target_locale=locale,
        )

    def _apply_tm_selection(self) -> None:
        if not (self._current_model and self._current_pf):
            return
        items = self._tm_list.selectedItems()
        if not items:
            return
        match = items[0].data(Qt.UserRole)
        plan = self._tm_workflow.build_apply_plan(
            match if isinstance(match, TMMatch) else None
        )
        if plan is None:
            return
        current = self.table.currentIndex()
        if not current.isValid():
            return
        value_index = self._current_model.index(current.row(), 2)
        self._current_model.setData(value_index, plan.target_text, Qt.EditRole)
        if plan.mark_for_review:
            status_index = self._current_model.index(current.row(), 3)
            self._current_model.setData(status_index, Status.FOR_REVIEW, Qt.EditRole)
        self._update_status_combo_from_selection()

    def _update_tm_suggestions(self) -> None:
        policy = self._tm_query_policy()
        lookup = self._current_tm_lookup()
        refresh = self._tm_workflow.build_refresh_plan(
            has_store=self._tm_store is not None,
            panel_index=self._left_stack.currentIndex(),
            lookup=lookup,
            policy=policy,
            has_current_file=self._current_pf is not None,
            tm_panel_index=1,
        )
        if not refresh.run_update:
            return
        assert self._tm_store is not None
        if refresh.flush_current_file and self._current_pf:
            self._flush_tm_updates(paths=[self._current_pf.path])
        assert refresh.query_plan is not None
        plan = refresh.query_plan
        if plan.mode == "cached" and plan.matches is not None:
            self._show_tm_matches(plan.matches)
            return
        self._tm_status_label.setText(plan.message)
        self._tm_list.clear()
        self._tm_apply_btn.setEnabled(False)
        self._set_tm_preview(
            self._tm_workflow.build_selection_plan(match=None, lookup=None)
        )
        if plan.mode == "query" and plan.cache_key is not None:
            self._start_tm_query(plan.cache_key)

    def _start_tm_query(self, cache_key: TMQueryKey) -> None:
        if not self._tm_store or self._tm_query_pool is None:
            return
        if (
            self._tm_query_key == cache_key
            and self._tm_query_future is not None
            and not self._tm_query_future.done()
        ):
            return
        self._tm_query_key = cache_key
        request = self._tm_workflow.build_query_request(cache_key)
        self._tm_query_future = self._tm_query_pool.submit(
            TMStore.query_path,
            self._tm_store.db_path,
            request.source_text,
            source_locale=request.source_locale,
            target_locale=request.target_locale,
            limit=request.limit,
            min_score=request.min_score,
            origins=request.origins,
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
        lookup = self._current_tm_lookup()
        show_current = self._tm_workflow.accept_query_result(
            cache_key=cache_key,
            matches=matches,
            lookup=lookup,
            policy=self._tm_query_policy(),
        )
        if not show_current:
            return
        self._show_tm_matches(matches)

    def _show_tm_matches(self, matches: list[TMMatch]) -> None:
        self._tm_list.clear()
        view = self._tm_workflow.build_suggestions_view(
            matches=matches,
            policy=self._tm_query_policy(),
            source_preview_limit=60,
            target_preview_limit=80,
        )
        self._tm_status_label.setText(view.message)
        if not view.items:
            self._tm_apply_btn.setEnabled(False)
            self._set_tm_preview(
                self._tm_workflow.build_selection_plan(match=None, lookup=None)
            )
            return
        for view_item in view.items:
            item = QListWidgetItem(view_item.label)
            item.setData(Qt.UserRole, view_item.match)
            item.setToolTip(view_item.tooltip_html)
            self._tm_list.addItem(item)
        if self._tm_list.count():
            self._tm_list.setCurrentRow(0)
        else:
            self._set_tm_preview(
                self._tm_workflow.build_selection_plan(match=None, lookup=None)
            )
            self._tm_apply_btn.setEnabled(False)

    def _tooltip_html(self, text: str) -> str:
        escaped = html.escape(text)
        return f'<span style="white-space: pre-wrap;">{escaped}</span>'

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
        if not self._save_exit_flow_service.should_accept_close(
            prompt_write_on_exit=self._prompt_write_on_exit,
            write_cache=self._write_cache_current,
            list_draft_files=self._draft_files,
            choose_action=self._show_save_files_dialog,
            save_all=self._save_all_files,
        ):
            event.ignore()
            return
        self._stop_timers()
        self._disconnect_system_theme_sync()
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
