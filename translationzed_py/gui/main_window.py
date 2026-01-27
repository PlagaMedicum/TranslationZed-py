from __future__ import annotations

import re
from pathlib import Path

import xxhash
from PySide6.QtCore import QByteArray, QItemSelectionModel, QTimer, Qt
from PySide6.QtGui import QAction, QGuiApplication, QKeySequence
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QTableView,
    QToolBar,
    QTreeView,
)
from shiboken6 import isValid

from translationzed_py.core import LocaleMeta, ParsedFile, parse, scan_root
from translationzed_py.core.model import Status
from translationzed_py.core.saver import save
from translationzed_py.core.app_config import load as _load_app_config
from translationzed_py.core.en_hash_cache import compute as _compute_en_hashes
from translationzed_py.core.en_hash_cache import read as _read_en_hash_cache
from translationzed_py.core.en_hash_cache import write as _write_en_hash_cache
from translationzed_py.core.preferences import load as _load_preferences
from translationzed_py.core.preferences import save as _save_preferences
from translationzed_py.core.status_cache import CacheEntry, read as _read_status_cache
from translationzed_py.core.status_cache import write as _write_status_cache
from translationzed_py.core import crash_recovery as _crash_recovery

from .entry_model import TranslationModel
from .fs_model import FsModel
from .commands import ChangeStatusCommand
from .delegates import StatusDelegate
from .dialogs import LocaleChooserDialog, SaveFilesDialog


class MainWindow(QMainWindow):
    """Main window: left file-tree, right translation table."""

    def __init__(
        self, project_root: str | None = None, *, selected_locales: list[str] | None = None
    ) -> None:
        super().__init__()
        self._startup_aborted = False
        self._root = Path(project_root or ".").resolve()
        self.setWindowTitle(f"TranslationZed – {self._root}")
        self._locales: dict[str, LocaleMeta] = {}
        self._selected_locales: list[str] = []
        self._current_encoding = "utf-8"
        self._app_config = _load_app_config(self._root)
        self._current_pf = None  # type: translationzed_py.core.model.ParsedFile | None
        self._current_model: TranslationModel | None = None
        self._opened_files: set[Path] = set()
        self._cache_map: dict[int, CacheEntry] = {}
        self._en_cache: dict[Path, ParsedFile] = {}
        self._child_windows: list[MainWindow] = []

        if not self._check_en_hash_cache():
            self._startup_aborted = True
            return
        if not self._check_crash_recovery():
            self._startup_aborted = True
            return
        prefs = _load_preferences(self._root)
        self._prompt_write_on_exit = bool(prefs.get("prompt_write_on_exit", True))
        self._wrap_text = bool(prefs.get("wrap_text", False))
        self._last_locales = list(prefs.get("last_locales", []) or [])
        self._last_root = str(prefs.get("last_root", "") or self._root)
        self._prefs_extras = dict(prefs.get("__extras__", {}))
        geom = str(prefs.get("window_geometry", "")).strip()
        if geom:
            try:
                self.restoreGeometry(QByteArray.fromBase64(geom.encode("ascii")))
            except Exception:
                pass

        splitter = QSplitter(self)
        self.setCentralWidget(splitter)

        # ── toolbar ────────────────────────────────────────────────────────
        self.toolbar = QToolBar("Toolbar", self)
        self.toolbar.setMovable(False)
        self.addToolBar(self.toolbar)
        self._updating_status_combo = False
        self.toolbar.addWidget(QLabel("Status", self))
        self.status_combo = QComboBox(self)
        self.status_combo.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        for st in Status:
            self.status_combo.addItem(st.name.title(), st)
        self.status_combo.setCurrentIndex(-1)
        self.status_combo.setEnabled(False)
        self.status_combo.currentIndexChanged.connect(self._status_combo_changed)
        self.toolbar.addWidget(self.status_combo)
        self.toolbar.addSeparator()
        self.search_mode = QComboBox(self)
        self.search_mode.addItem("Key", 0)
        self.search_mode.addItem("Source", 1)
        self.search_mode.addItem("Trans", 2)
        self.search_mode.currentIndexChanged.connect(self._schedule_search)
        self.toolbar.addWidget(self.search_mode)
        self.regex_check = QCheckBox("Regex", self)
        self.regex_check.stateChanged.connect(self._schedule_search)
        self.toolbar.addWidget(self.regex_check)
        self.search_edit = QLineEdit(self)
        self.search_edit.setPlaceholderText("Search")
        self.search_edit.textChanged.connect(self._schedule_search)
        self.toolbar.addWidget(self.search_edit)
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(300)
        self._search_timer.timeout.connect(self._run_search)
        self._search_matches: list[int] = []
        self._search_index = -1
        self._search_column = 0

        # ── menu bar ───────────────────────────────────────────────────────
        menubar = self.menuBar()
        self.menu_project = menubar.addMenu("Project")
        self.menu_edit = menubar.addMenu("Edit")
        self.menu_view = menubar.addMenu("View")

        # ── left pane: project tree ──────────────────────────────────────────
        self.tree = QTreeView()
        self._init_locales(selected_locales)
        if not self._selected_locales:
            self._startup_aborted = True
            return
        self.fs_model = FsModel(self._root, [self._locales[c] for c in self._selected_locales])
        self.tree.setModel(self.fs_model)
        # prevent in-place renaming on double-click; we use double-click to open
        self.tree.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tree.expandAll()
        self.tree.activated.connect(self._file_chosen)  # Enter / platform activation
        self.tree.doubleClicked.connect(self._file_chosen)
        splitter.addWidget(self.tree)

        # ── proofread toggle ────────────────────────────────────────────────
        act_proof = QAction("&Mark Proofread", self)
        act_proof.setShortcut("Ctrl+P")
        act_proof.triggered.connect(self._mark_proofread)
        self.addAction(act_proof)
        self.act_proof = act_proof

        # ── right pane: entry table ─────────────────────────────────────────
        self.table = QTableView()
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setWordWrap(self._wrap_text)
        self._status_delegate = StatusDelegate(self.table)
        self.table.setItemDelegateForColumn(3, self._status_delegate)
        splitter.addWidget(self.table)

        splitter.setSizes([220, 600])

        # ── undo/redo actions ───────────────────────────────────────────────
        self.act_undo: QAction | None = None
        self.act_redo: QAction | None = None

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
        self.menu_project.addAction(act_open)
        self.menu_project.addAction(act_save)
        self.menu_project.addAction(act_switch)
        self.menu_project.addSeparator()
        self.menu_project.addAction(act_exit)

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
        act_prompt = QAction("Prompt on E&xit", self)
        act_prompt.setCheckable(True)
        act_prompt.setChecked(self._prompt_write_on_exit)
        act_prompt.triggered.connect(self._toggle_prompt_on_exit)
        self.addAction(act_prompt)
        self.menu_view.addAction(act_wrap)
        self.menu_view.addAction(act_prompt)

        # ── cache ──────────────────────────────────────────────────────

    def _init_locales(self, selected_locales: list[str] | None) -> None:
        self._locales = scan_root(self._root)
        selectable = {k: v for k, v in self._locales.items() if k != "EN"}

        if selected_locales is None:
            dialog = LocaleChooserDialog(
                selectable.values(), self, preselected=self._last_locales
            )
            if dialog.exec() != dialog.DialogCode.Accepted:
                self._selected_locales = []
                return
            selected_locales = dialog.selected_codes()

        self._selected_locales = [c for c in selected_locales if c in selectable]

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

    def _load_en_source(self, path: Path, locale: str | None) -> dict[str, str]:
        en_path = self._en_path_for(path, locale)
        if not en_path:
            return {}
        if en_path in self._en_cache:
            pf = self._en_cache[en_path]
        else:
            en_meta = self._locales.get("EN")
            encoding = en_meta.charset if en_meta else "utf-8"
            try:
                pf = parse(en_path, encoding=encoding)
            except Exception:
                return {}
            self._en_cache[en_path] = pf
        return {e.key: e.value for e in pf.entries}

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

    def _check_crash_recovery(self) -> bool:
        rec = _crash_recovery.read()
        if not rec:
            return True
        rec_root = rec.get("root")
        if not isinstance(rec_root, str):
            return True
        try:
            if Path(rec_root).resolve() != self._root:
                return True
        except Exception:
            return True
        files = rec.get("files", [])
        if not isinstance(files, list) or not files:
            _crash_recovery.clear()
            return True
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Warning)
        msg.setWindowTitle("Recovery data found")
        msg.setText("A previous session ended unexpectedly.")
        msg.setInformativeText(
            "Drafts are stored in cache. Restore to keep them, or Discard to remove cached drafts."
        )
        preview = "\n".join(files[:8])
        if len(files) > 8:
            preview += f"\n… {len(files) - 8} more"
        msg.setDetailedText(preview)
        btn_restore = msg.addButton("Restore", QMessageBox.AcceptRole)
        btn_discard = msg.addButton("Discard", QMessageBox.DestructRole)
        msg.exec()
        if msg.clickedButton() is btn_discard:
            _crash_recovery.discard_cache(self._root, files)
        _crash_recovery.clear()
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
        self._opened_files.clear()
        self._current_pf = None
        self._current_model = None
        self.table.setModel(None)
        self._set_status_combo(None)
        self.fs_model = FsModel(self._root, [self._locales[c] for c in self._selected_locales])
        self.tree.setModel(self.fs_model)
        self.tree.expandAll()

    def _file_chosen(self, index) -> None:
        """Populate table when user activates a translation file."""
        raw_path = index.data(Qt.UserRole)  # FsModel stores absolute path string
        path = Path(raw_path) if raw_path else None
        if not (path and path.suffix == self._app_config.translation_ext):
            return
        if not self._write_cache_current():
            return
        locale = self._locale_for_path(path)
        encoding = self._locales.get(locale, LocaleMeta("", Path(), "", "utf-8")).charset
        try:
            pf = parse(path, encoding=encoding)
        except Exception as exc:
            QMessageBox.warning(self, "Parse error", f"{path}\n\n{exc}")
            return

        self._current_encoding = encoding

        base_values = {e.key: e.value for e in pf.entries}
        source_values = self._load_en_source(path, locale)
        self._cache_map = _read_status_cache(self._root, path)
        changed_keys: set[str] = set()
        for idx, e in enumerate(pf.entries):
            h = xxhash.xxh64(e.key.encode("utf-8")).intdigest() & 0xFFFF
            if h not in self._cache_map:
                continue
            rec = self._cache_map[h]
            new_value = rec.value if rec.value is not None else e.value
            if rec.value is not None and rec.value != e.value:
                changed_keys.add(e.key)
            if new_value != e.value or rec.status != e.status:
                pf.entries[idx] = type(e)(
                    e.key,
                    new_value,
                    rec.status,
                    e.span,
                    e.segments,
                    e.gaps,
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
            base_values=base_values,
            changed_keys=changed_keys,
            source_values=source_values,
        )
        self._current_model.dataChanged.connect(self._on_model_changed)
        self._current_model.dataChanged.connect(self._on_model_data_changed)
        self.table.setModel(self._current_model)
        self.table.selectionModel().currentChanged.connect(self._on_selection_changed)
        self._update_status_combo_from_selection()
        if self.search_edit.text():
            self._schedule_search()
        if changed_keys:
            self.fs_model.set_dirty(self._current_pf.path, True)

        # (re)create undo/redo actions bound to this file’s stack
        for old in (self.act_undo, self.act_redo):
            if old and isValid(old):
                if old in self.menu_edit.actions():
                    self.menu_edit.removeAction(old)
                self.removeAction(old)
                old.deleteLater()
        stack = self._current_model.undo_stack
        self.act_undo = stack.createUndoAction(self, "&Undo")
        self.act_redo = stack.createRedoAction(self, "&Redo")
        self.act_undo.setShortcut(QKeySequence.StandardKey.Undo)
        self.act_redo.setShortcut(QKeySequence.StandardKey.Redo)
        for a in (self.act_undo, self.act_redo):
            self.addAction(a)
        if self.menu_edit.actions():
            first = self.menu_edit.actions()[0]
            self.menu_edit.insertAction(first, self.act_redo)
            self.menu_edit.insertAction(first, self.act_undo)
        else:
            self.menu_edit.addAction(self.act_undo)
            self.menu_edit.addAction(self.act_redo)


    def _save_current(self) -> bool:
        """Patch file on disk if there are unsaved value edits."""
        if not (self._current_pf and self._current_model):
            return True
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
            )

            self._current_model.reset_baseline()
            self.fs_model.set_dirty(self._current_pf.path, False)
            self._update_recovery_marker()
        except Exception as exc:
            QMessageBox.critical(self, "Save failed", str(exc))
            return False
        return True

    def _request_write_original(self) -> None:
        self._write_cache_current()
        files = self._draft_files()
        if not files:
            QMessageBox.information(self, "Nothing to write", "No draft changes to write.")
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
            cached = _read_status_cache(self._root, original)
            if any(entry.value is not None for entry in cached.values()):
                files.append(original)
        return sorted(set(files))

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
        self._update_recovery_marker()

    def _save_file_from_cache(self, path: Path) -> bool:
        cached = _read_status_cache(self._root, path)
        if not any(entry.value is not None for entry in cached.values()):
            return True
        locale = self._locale_for_path(path)
        encoding = self._locales.get(locale, LocaleMeta("", Path(), "", "utf-8")).charset
        try:
            pf = parse(path, encoding=encoding)
        except Exception as exc:
            QMessageBox.warning(self, "Parse error", f"{path}\n\n{exc}")
            return False
        changed: dict[str, str] = {}
        new_entries = []
        for e in pf.entries:
            h = xxhash.xxh64(e.key.encode("utf-8")).intdigest() & 0xFFFF
            rec = cached.get(h)
            if rec is None:
                new_entries.append(e)
                continue
            if rec.status != e.status:
                e = type(e)(e.key, e.value, rec.status, e.span, e.segments, e.gaps)
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
        try:
            _write_status_cache(
                self._root,
                self._current_pf.path,
                self._current_pf.entries,
                changed_keys=self._current_model.changed_keys(),
            )
        except Exception as exc:
            QMessageBox.critical(self, "Cache write failed", str(exc))
            return False
        if self._current_model.changed_keys():
            self.fs_model.set_dirty(self._current_pf.path, True)
        else:
            self.fs_model.set_dirty(self._current_pf.path, False)
        self._update_recovery_marker()
        return True

    def _on_model_changed(self, *_args) -> None:
        if not (self._current_pf and self._current_model):
            return
        self._write_cache_current()

    def _update_recovery_marker(self) -> None:
        files = self._draft_files()
        _crash_recovery.write(self._root, files)

    def _focus_search(self) -> None:
        self.search_edit.setFocus()
        self.search_edit.selectAll()

    def _schedule_search(self, *_args) -> None:
        if self._search_timer.isActive():
            self._search_timer.stop()
        self._search_timer.start()

    def _run_search(self) -> None:
        if not self._current_model:
            self._search_matches = []
            self._search_index = -1
            return
        query = self.search_edit.text()
        if not query:
            self._search_matches = []
            self._search_index = -1
            return
        column = int(self.search_mode.currentData())
        self._search_column = column
        use_regex = self.regex_check.isChecked()
        matcher = None
        if use_regex:
            try:
                matcher = re.compile(query, re.IGNORECASE)
            except re.error:
                self._search_matches = []
                self._search_index = -1
                return
        else:
            query = query.lower()

        matches: list[int] = []
        for row in range(self._current_model.rowCount()):
            index = self._current_model.index(row, column)
            value = index.data(Qt.DisplayRole)
            text = "" if value is None else str(value)
            if matcher:
                if matcher.search(text):
                    matches.append(row)
            else:
                if query in text.lower():
                    matches.append(row)
        self._search_matches = matches
        if not matches:
            self._search_index = -1
            return
        self._search_index = 0
        self._select_match(0)

    def _ensure_search_ready(self) -> None:
        if self._search_timer.isActive():
            self._search_timer.stop()
            self._run_search()

    def _select_match(self, idx: int) -> None:
        if not self._current_model or not self._search_matches:
            return
        row = self._search_matches[idx]
        column = self._search_column
        model_index = self._current_model.index(row, column)
        self.table.selectionModel().setCurrentIndex(
            model_index,
            QItemSelectionModel.ClearAndSelect | QItemSelectionModel.Rows,
        )
        self.table.scrollTo(model_index, QAbstractItemView.PositionAtCenter)

    def _search_next(self) -> None:
        self._ensure_search_ready()
        if not self._search_matches:
            return
        self._search_index = (self._search_index + 1) % len(self._search_matches)
        self._select_match(self._search_index)

    def _search_prev(self) -> None:
        self._ensure_search_ready()
        if not self._search_matches:
            return
        self._search_index = (self._search_index - 1) % len(self._search_matches)
        self._select_match(self._search_index)

    def _copy_selection(self) -> None:
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
        self._current_model.setData(idx, text, Qt.EditRole)

    def _toggle_wrap_text(self, checked: bool) -> None:
        self._wrap_text = bool(checked)
        self.table.setWordWrap(self._wrap_text)
        self.table.resizeRowsToContents()
        self._persist_preferences()

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
            "wrap_text": self._wrap_text,
            "last_root": str(self._root),
            "last_locales": list(self._selected_locales),
            "window_geometry": geometry,
            "__extras__": dict(self._prefs_extras),
        }
        try:
            _save_preferences(prefs, self._root)
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
        if top_left.row() <= row <= bottom_right.row():
            if roles is None or Qt.EditRole in roles or Qt.DisplayRole in roles:
                self._update_status_combo_from_selection()

    def _on_selection_changed(self, _current, _previous) -> None:
        self._update_status_combo_from_selection()

    def _update_status_combo_from_selection(self) -> None:
        if not self._current_model:
            self._set_status_combo(None)
            return
        current = self.table.currentIndex()
        if not current.isValid():
            self._set_status_combo(None)
            return
        status = self._current_model.status_for_row(current.row())
        self._set_status_combo(status)

    def _set_status_combo(self, status: Status | None) -> None:
        self._updating_status_combo = True
        try:
            if status is None:
                self.status_combo.setEnabled(False)
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
        current = self.table.currentIndex()
        if not current.isValid():
            return
        status = self.status_combo.currentData()
        if status is None:
            return
        model_index = self._current_model.index(current.row(), 3)
        self._current_model.setData(model_index, status, Qt.EditRole)

    def _mark_proofread(self) -> None:
        if not (self._current_pf and self._current_model):
            return
        idx = self.table.currentIndex()
        if not idx.isValid():
            return
        row = idx.row()
        cmd = ChangeStatusCommand(
            self._current_pf, row, Status.PROOFREAD, self._current_model
        )
        self._current_model.undo_stack.push(cmd)
        self._write_cache_current()
        self._update_status_combo_from_selection()

    def closeEvent(self, event) -> None:  # noqa: N802
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
        self._persist_preferences()
        _crash_recovery.clear()
        event.accept()
