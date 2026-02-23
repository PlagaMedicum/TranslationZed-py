"""Extracted MainWindow EN-diff and insertion helper methods."""

from __future__ import annotations

import contextlib
from collections.abc import Mapping, Sequence
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QVBoxLayout,
)

from translationzed_py.core import LocaleMeta, ParsedFile, parse
from translationzed_py.core.atomic_io import write_text_atomic as _write_text_atomic
from translationzed_py.core.en_diff_service import (
    classify_file as _classify_en_diff_file,
)
from translationzed_py.core.en_diff_snapshot import (
    read_snapshot as _read_en_diff_snapshot,
)
from translationzed_py.core.en_diff_snapshot import (
    update_file_snapshot as _update_en_diff_snapshot,
)
from translationzed_py.core.en_insert_plan import ENInsertPlan as _ENInsertPlan
from translationzed_py.core.en_insert_plan import (
    apply_insert_plan as _apply_en_insert_plan,
)
from translationzed_py.core.en_insert_plan import (
    build_insert_plan as _build_en_insert_plan,
)
from translationzed_py.core.source_reference_service import (
    reference_path_for as _reference_path_for,
)

from .entry_model import VirtualNewRow


def _stash_current_new_row_drafts(win) -> None:
    if not (win._current_pf and win._current_model):
        return
    drafts = win._current_model.edited_virtual_new_values()
    if drafts:
        win._en_new_drafts_by_file[win._current_pf.path] = dict(drafts)
    else:
        win._en_new_drafts_by_file.pop(win._current_pf.path, None)


def _en_reference_path_for_locale_file(win, path: Path) -> Path | None:
    locale = win._locale_for_path(path)
    if not locale or locale == "EN":
        return None
    en_path = _reference_path_for(
        win._root,
        path,
        target_locale=locale,
        reference_locale="EN",
    )
    if en_path is not None and en_path.exists():
        return en_path
    return None


def _read_file_text(win, path: Path, *, encoding: str) -> str:
    return path.read_text(encoding=encoding)


def _load_en_reference_data(
    win,
    locale_path: Path,
) -> tuple[Path | None, str, dict[str, str], tuple[str, ...]]:
    en_path = win._en_reference_path_for_locale_file(locale_path)
    if en_path is None:
        return None, "", {}, ()
    en_meta = win._locales.get("EN", LocaleMeta("", Path(), "", "utf-8"))
    en_encoding = en_meta.charset or "utf-8"
    try:
        en_parsed = parse(en_path, encoding=en_encoding)
    except Exception:
        return en_path, "", {}, ()
    values = {entry.key: entry.value for entry in en_parsed.entries}
    order = tuple(entry.key for entry in en_parsed.entries)
    rel_key = ""
    with contextlib.suppress(ValueError):
        rel_key = en_path.relative_to(win._root).as_posix()
    return en_path, rel_key, values, order


def _build_en_diff_model_state(
    win,
    *,
    path: Path,
    parsed_file: ParsedFile,
    en_rel_key: str,
    en_values: Mapping[str, str],
    en_order: Sequence[str],
) -> tuple[dict[str, str], list[VirtualNewRow], tuple[str, ...]]:
    # If EN reference cannot be resolved/parsed for this file, disable diff badges
    # instead of incorrectly marking all locale keys as REMOVED.
    if not en_rel_key:
        return {}, [], ()
    locale_values = {entry.key: entry.value for entry in parsed_file.entries}
    snapshot = _read_en_diff_snapshot(win._root)
    snapshot_rows = snapshot.get(en_rel_key, {}) if en_rel_key else {}
    diff_result = _classify_en_diff_file(
        en_values=en_values,
        locale_values=locale_values,
        snapshot_rows=snapshot_rows,
    )
    markers: dict[str, str] = {}
    for key in diff_result.removed_keys:
        markers[key] = "REMOVED"
    for key in diff_result.modified_keys:
        markers[key] = "MODIFIED"
    drafts = win._en_new_drafts_by_file.get(path, {})
    virtual_rows: list[VirtualNewRow] = []
    for key in diff_result.new_keys:
        source = str(en_values.get(key, ""))
        value = str(drafts.get(key, ""))
        virtual_rows.append(VirtualNewRow(key=key, source=source, value=value))
        markers[key] = "NEW"
    edited_keys = tuple(drafts)
    return markers, virtual_rows, edited_keys


def _refresh_current_en_diff_state(win) -> None:
    if not (win._current_pf and win._current_model):
        return
    win._stash_current_new_row_drafts()
    markers, virtual_rows, edited_keys = win._build_en_diff_model_state(
        path=win._current_pf.path,
        parsed_file=win._current_pf,
        en_rel_key=win._current_en_reference_rel,
        en_values=win._current_en_values,
        en_order=win._current_en_order,
    )
    win._current_model.apply_diff_state(
        marker_by_key=markers,
        virtual_new_rows=virtual_rows,
        en_order_keys=win._current_en_order,
        edited_virtual_new_keys=edited_keys,
    )


def _update_en_snapshot_for_locale_file(win, path: Path) -> None:
    _en_path, en_rel, en_values, _en_order = win._load_en_reference_data(path)
    if not en_rel or not en_values:
        return
    _update_en_diff_snapshot(
        win._root,
        en_rel,
        en_values,
    )


def _insertion_enabled_for_path(win, path: Path) -> bool:
    locale = win._locale_for_path(path)
    if not locale or locale == "EN":
        return False
    try:
        rel = path.relative_to(win._root).as_posix()
    except ValueError:
        rel = path.name
    globs = tuple(win._app_config.insertion_enabled_globs or ())
    if not globs:
        return False
    return any(
        path.match(glob) or Path(rel).match(glob) or path.name == glob for glob in globs
    )


def _build_en_insert_preview_text(
    win,
    *,
    locale_text: str,
    plan: _ENInsertPlan,
    context_lines: int,
) -> str:
    if not plan.items:
        return "No NEW rows to insert."
    locale_lines = locale_text.splitlines()
    key_line_map: dict[str, int] = {}
    for idx, line in enumerate(locale_lines):
        if "=" not in line:
            continue
        key = line.split("=", 1)[0].strip()
        if key and key not in key_line_map:
            key_line_map[key] = idx
    blocks: list[str] = []
    pad = max(0, int(context_lines))
    for item in plan.items:
        anchor = item.anchor_key
        anchor_idx = key_line_map.get(anchor, -1) if anchor else -1
        if anchor_idx >= 0:
            before_start = max(0, anchor_idx - pad)
            before = locale_lines[before_start : anchor_idx + 1]
            after = locale_lines[anchor_idx + 1 : anchor_idx + 1 + pad]
        else:
            before = locale_lines[:pad]
            after = locale_lines[pad : pad * 2] if pad > 0 else []
        block_lines = [
            f"Key: {item.key}",
            f"Anchor: {anchor or '<file-start>'}",
            "--- context before ---",
            *(before or ["<none>"]),
            "--- insertion ---",
            *item.snippet_lines,
            "--- context after ---",
            *(after or ["<none>"]),
        ]
        blocks.append("\n".join(block_lines))
    return "\n\n".join(blocks)


def _parse_insert_edit_payload(
    win,
    text: str,
    *,
    expected_keys: Sequence[str],
) -> dict[str, str] | None:
    lines = text.splitlines()
    current_key = ""
    bucket: dict[str, list[str]] = {}
    for line in lines:
        if line.startswith("### KEY: "):
            current_key = line[len("### KEY: ") :].strip()
            if current_key:
                bucket.setdefault(current_key, [])
            continue
        if current_key:
            bucket[current_key].append(line)
    if not bucket:
        return None
    expected = {str(key).strip() for key in expected_keys if str(key).strip()}
    if set(bucket) != expected:
        return None
    return {key: "\n".join(lines).rstrip("\n") for key, lines in bucket.items()}


def _prompt_insert_snippet_edits(
    win,
    *,
    plan: _ENInsertPlan,
    preview_text: str,
) -> dict[str, str] | None:
    if win._test_mode:
        return None
    editable_seed = "\n\n".join(
        "\n".join([f"### KEY: {item.key}", *item.snippet_lines]) for item in plan.items
    )
    dialog = QDialog(win)
    dialog.setWindowTitle("Edit NEW insertion snippets")
    dialog.resize(860, 620)
    layout = QVBoxLayout(dialog)
    layout.setContentsMargins(8, 8, 8, 8)
    layout.setSpacing(6)
    hint = QLabel(
        "Edit insertion snippets only. Keep section headers unchanged.",
        dialog,
    )
    layout.addWidget(hint)
    context_view = QPlainTextEdit(dialog)
    context_view.setReadOnly(True)
    context_view.setPlainText(preview_text)
    context_view.setLineWrapMode(QPlainTextEdit.NoWrap)
    context_view.setMinimumHeight(220)
    layout.addWidget(context_view, 1)
    editor = QPlainTextEdit(dialog)
    editor.setPlainText(editable_seed)
    editor.setLineWrapMode(QPlainTextEdit.NoWrap)
    layout.addWidget(editor, 1)
    buttons = QDialogButtonBox(
        QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
        dialog,
    )
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    layout.addWidget(buttons)
    if dialog.exec() != dialog.DialogCode.Accepted:
        return None
    parsed = win._parse_insert_edit_payload(
        editor.toPlainText(),
        expected_keys=[item.key for item in plan.items],
    )
    if parsed is None:
        QMessageBox.warning(
            win,
            "Invalid snippet edit",
            "Snippet sections are invalid. Keep `### KEY:` headers unchanged.",
        )
        return None
    return parsed


def _prompt_new_row_insertion_action(
    win,
    *,
    rel_path: str,
    preview_text: str,
    plan: _ENInsertPlan,
) -> tuple[str, dict[str, str] | None]:
    if win._test_mode:
        return "skip", None
    while True:
        msg = QMessageBox(win)
        msg.setIcon(QMessageBox.Question)
        msg.setWindowTitle("Apply NEW rows")
        msg.setText(f"Edited NEW rows were found for {rel_path}.")
        msg.setInformativeText(
            "Apply inserts snippets preserving EN order and comments."
        )
        msg.setDetailedText(preview_text)
        apply_btn = msg.addButton("Apply", QMessageBox.AcceptRole)
        skip_btn = msg.addButton("Skip", QMessageBox.ActionRole)
        edit_btn = msg.addButton("Edit", QMessageBox.ActionRole)
        cancel_btn = msg.addButton("Cancel", QMessageBox.RejectRole)
        msg.exec()
        clicked = msg.clickedButton()
        if clicked is apply_btn:
            return "apply", None
        if clicked is skip_btn:
            return "skip", None
        if clicked is cancel_btn or clicked is None:
            return "cancel", None
        if clicked is edit_btn:
            edited = win._prompt_insert_snippet_edits(
                plan=plan,
                preview_text=preview_text,
            )
            if edited is None:
                continue
            return "apply", edited


def _apply_new_row_insertions(
    win,
    *,
    path: Path,
    edited_new_values: Mapping[str, str],
    edited_snippets: Mapping[str, str] | None = None,
    en_path: Path | None = None,
    locale_encoding: str | None = None,
) -> bool:
    if not edited_new_values:
        return True
    en_path = en_path or win._current_en_reference_path
    if en_path is None:
        return True
    en_encoding = (
        win._locales.get("EN", LocaleMeta("", Path(), "", "utf-8")).charset or "utf-8"
    )
    target_encoding = locale_encoding or win._current_encoding
    try:
        en_text = win._read_file_text(en_path, encoding=en_encoding)
        locale_text = win._read_file_text(path, encoding=target_encoding)
    except OSError as exc:
        QMessageBox.warning(win, "Insertion failed", str(exc))
        return False
    plan = _build_en_insert_plan(
        en_text=en_text,
        locale_text=locale_text,
        edited_new_values=edited_new_values,
        comment_prefixes=(win._app_config.comment_prefix, "#", "--"),
    )
    if not plan.items:
        return True
    merged = _apply_en_insert_plan(
        locale_text=locale_text,
        plan=plan,
        edited_snippets=edited_snippets,
    )
    try:
        _write_text_atomic(path, merged, encoding=target_encoding)
    except OSError as exc:
        QMessageBox.warning(win, "Insertion failed", str(exc))
        return False
    return True
