"""Committed EN document and change-classification contracts."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from translationzed_py.core.git_sync import inspect, resolve_commit
from translationzed_py.core.git_sync_service import (
    GitFileDelta,
    GitSyncChangeSet,
    GitSyncDocumentError,
    GitSyncItemChoice,
    build_change_set,
    build_merge_plan,
    classify_documents,
    parse_source_document,
    resolve_merge_plan,
)
from translationzed_py.core.model import Entry, Status
from translationzed_py.core.parser import parse
from translationzed_py.core.project_scanner import LocaleMeta
from translationzed_py.core.status_cache import write as write_status_cache


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ("git", "-C", str(root), *args),
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _document(path: str, text: str):
    return parse_source_document(
        path=path,
        raw=text.encode("utf-8"),
        encoding="utf-8",
    )


def test_classify_documents_combines_value_comments_membership_and_order() -> None:
    """Classify every supported key-level change without losing source order."""
    base = _document(
        "EN/UI.txt",
        '-- old A\nA = "Old"\nB = "Removed"\nC = "Stable"\n',
    )
    head = _document(
        "EN/UI.txt",
        'C = "Stable"\n-- new A\nA = "New"\n-- new D\nD = "Added"\n',
    )

    deltas = classify_documents(base, head)

    by_key = {delta.key: delta for delta in deltas}
    assert by_key["C"].kinds == ("reordered",)
    assert by_key["A"].kinds == ("modified", "comments", "reordered")
    assert by_key["D"].kinds == ("added",)
    assert by_key["D"].head_comments == ("-- new D",)
    assert by_key["B"].kinds == ("removed",)
    assert [delta.key for delta in deltas] == ["C", "A", "D", "B"]


def test_parse_source_document_uses_json_and_raw_file_contracts() -> None:
    """Parse committed JSON and raw text through the production format contracts."""
    json_doc = parse_source_document(
        path="EN/UI.json",
        raw=b'{"B": "two", "A": "one"}',
        encoding="cp1251",
    )
    raw_doc = parse_source_document(
        path="EN/description.txt",
        raw="One description".encode("cp1251"),
        encoding="cp1251",
    )

    assert [(row.key, row.value) for row in json_doc.rows] == [
        ("B", "two"),
        ("A", "one"),
    ]
    assert json_doc.rows[0].leading_comments == ()
    assert [(row.key, row.value) for row in raw_doc.rows] == [
        ("description.txt", "One description")
    ]


def test_parse_source_document_rejects_duplicates_and_oversize(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reject ambiguous keys and blobs beyond the synchronization limit."""
    with pytest.raises(GitSyncDocumentError, match="Duplicate"):
        _document("EN/UI.txt", 'A = "one"\nA = "two"\n')

    monkeypatch.setattr(
        "translationzed_py.core.git_sync_service.MAX_SYNC_BLOB_BYTES", 3
    )
    with pytest.raises(GitSyncDocumentError, match="64 MiB"):
        _document("EN/UI.txt", 'A = "one"\n')


def test_build_change_set_reads_committed_blobs_and_preserves_file_rename(
    tmp_path: Path,
) -> None:
    """Read committed blobs and retain a renamed file's old and new paths."""
    root = tmp_path / "project"
    (root / "EN").mkdir(parents=True)
    _git(root, "init")
    _git(root, "config", "user.email", "tests@example.invalid")
    _git(root, "config", "user.name", "Tests")
    old_path = root / "EN" / "Old.txt"
    old_path.write_text(
        'A = "Old"\nB = "Stable B"\nC = "Stable C"\n',
        encoding="utf-8",
    )
    _git(root, "add", ".")
    _git(root, "commit", "-m", "baseline")
    baseline = resolve_commit(root)
    _git(root, "mv", "EN/Old.txt", "EN/New.txt")
    (root / "EN" / "New.txt").write_text(
        'A = "New"\nB = "Stable B"\nC = "Stable C"\n',
        encoding="utf-8",
    )
    _git(root, "commit", "-am", "rename and edit")
    inspection = inspect(root, baseline=baseline)

    change_set = build_change_set(root, inspection, en_encoding="utf-8")

    assert change_set.baseline == baseline
    assert len(change_set.files) == 1
    delta = change_set.files[0]
    assert (delta.kind, delta.previous_path, delta.path) == (
        "renamed",
        "EN/Old.txt",
        "EN/New.txt",
    )
    assert delta.error is None
    assert [(item.key, item.kinds) for item in delta.keys] == [("A", ("modified",))]


def test_build_change_set_contains_unreadable_blob_as_file_error(
    tmp_path: Path,
) -> None:
    """Contain an unreadable committed blob as a file-level preview error."""
    root = tmp_path / "project"
    (root / "EN").mkdir(parents=True)
    _git(root, "init")
    _git(root, "config", "user.email", "tests@example.invalid")
    _git(root, "config", "user.name", "Tests")
    path = root / "EN" / "UI.txt"
    path.write_text('A = "Old"\n', encoding="utf-8")
    _git(root, "add", ".")
    _git(root, "commit", "-m", "baseline")
    baseline = resolve_commit(root)
    path.write_bytes(b'\xff = "bad"\n')
    _git(root, "add", ".")
    _git(root, "commit", "-m", "invalid encoding")

    change_set = build_change_set(
        root,
        inspect(root, baseline=baseline),
        en_encoding="utf-8",
    )

    assert change_set.files[0].keys == ()
    assert change_set.files[0].error


def _merge_project(tmp_path: Path) -> tuple[Path, dict[str, LocaleMeta]]:
    root = tmp_path / "project"
    for code in ("EN", "BE"):
        locale = root / code
        locale.mkdir(parents=True)
        (locale / "language.txt").write_text(
            f"text = {code},\ncharset = UTF-8,\n",
            encoding="utf-8",
        )
    return root, {
        code: LocaleMeta(code, root / code, code, "utf-8") for code in ("EN", "BE")
    }


def test_build_merge_plan_preserves_target_draft_and_exposes_comment_conflict(
    tmp_path: Path,
) -> None:
    """Preserve target drafts and require an explicit divergent-comment choice."""
    root, locales = _merge_project(tmp_path)
    target = root / "BE" / "UI.txt"
    target.write_text(
        '-- лакальны A\n-- TZP:PROOFREAD\nA = "Target A"\n'
        'B = "Target B"\nC = "Target C"\n',
        encoding="utf-8",
    )
    parsed = parse(target)
    entries = list(parsed.entries)
    first = entries[0]
    entries[0] = Entry(
        first.key,
        "Draft A",
        Status.PROOFREAD,
        first.span,
        first.segments,
        first.gaps,
        first.raw,
        first.key_hash,
    )
    write_status_cache(
        root,
        target,
        entries,
        changed_keys={"A"},
        original_values={"A": "Target A"},
    )
    base = _document(
        "EN/UI.txt",
        '-- old A\nA = "Old A"\nB = "Old B"\nC = "Old C"\n',
    )
    head = _document(
        "EN/UI.txt",
        'C = "Old C"\n-- new A\nA = "New A"\nD = "New D"\n',
    )
    change_set = GitSyncChangeSet(
        baseline="a" * 40,
        head="b" * 40,
        files=(
            GitFileDelta(
                kind="modified",
                path="EN/UI.txt",
                previous_path=None,
                keys=classify_documents(base, head),
            ),
        ),
        dirty_paths=("EN/dirty.txt",),
    )

    plan = build_merge_plan(
        root,
        change_set,
        locales=locales,
        selected_locales=["BE"],
    )

    by_key = {item.key: item for item in plan.items}
    assert plan.dirty_paths == ("EN/dirty.txt",)
    assert by_key["A"].target_value == "Draft A"
    assert by_key["A"].target_file_value == "Target A"
    assert by_key["A"].target_status is Status.PROOFREAD
    assert by_key["A"].target_comments == ("-- лакальны A",)
    assert by_key["A"].default_decision == "conflict"
    assert by_key["A"].comment_decision == "choose"
    assert by_key["A"].propose_for_review is True
    assert by_key["D"].default_decision == "apply"
    assert by_key["D"].target_value is None
    assert by_key["B"].default_decision == "apply"

    resolved = resolve_merge_plan(
        plan,
        {
            by_key["A"].item_id: GitSyncItemChoice(
                item_id=by_key["A"].item_id,
                decision="apply",
                comment_decision="use_en",
                mark_for_review=True,
            )
        },
    )
    assert resolved.unresolved_item_ids == ()
    assert resolved.advance_baseline is True
    assert (
        next(
            choice
            for choice in resolved.choices
            if choice.item_id == by_key["A"].item_id
        ).mark_for_review
        is True
    )


def test_merge_plan_requires_ignore_or_retry_for_missing_target_file(
    tmp_path: Path,
) -> None:
    """Keep a missing target unresolved until the user explicitly ignores it."""
    root, locales = _merge_project(tmp_path)
    head = _document("EN/New.txt", 'A = "New"\n')
    change_set = GitSyncChangeSet(
        baseline="a" * 40,
        head="b" * 40,
        files=(
            GitFileDelta(
                kind="added",
                path="EN/New.txt",
                previous_path=None,
                keys=classify_documents(None, head),
            ),
        ),
    )

    plan = build_merge_plan(
        root,
        change_set,
        locales=locales,
        selected_locales=["BE"],
    )

    assert len(plan.items) == 1
    item = plan.items[0]
    assert item.kinds == ("file_missing",)
    assert item.can_apply is False
    assert resolve_merge_plan(plan).advance_baseline is False
    ignored = resolve_merge_plan(
        plan,
        {
            item.item_id: GitSyncItemChoice(
                item_id=item.item_id,
                decision="ignore",
            )
        },
    )
    assert ignored.advance_baseline is True


def test_merge_plan_rejects_excessive_preview_items(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Stop plan construction at the fixed item-count resource boundary."""
    root, locales = _merge_project(tmp_path)
    (root / "BE" / "UI.txt").write_text('C = "Target"\n', encoding="utf-8")
    head = _document("EN/UI.txt", 'A = "New A"\nB = "New B"\n')
    change_set = GitSyncChangeSet(
        baseline="a" * 40,
        head="b" * 40,
        files=(
            GitFileDelta(
                kind="added",
                path="EN/UI.txt",
                previous_path=None,
                keys=classify_documents(None, head),
            ),
        ),
    )
    monkeypatch.setattr(
        "translationzed_py.core.git_sync_service.MAX_SYNC_PLAN_ITEMS", 1
    )

    with pytest.raises(GitSyncDocumentError, match="exceeds 1 items"):
        build_merge_plan(
            root,
            change_set,
            locales=locales,
            selected_locales=["BE"],
        )


def test_merge_plan_maps_locale_suffix_and_flags_unresolved_rename(
    tmp_path: Path,
) -> None:
    """Map locale suffixes while exposing an unapplied target rename."""
    root, locales = _merge_project(tmp_path)
    old_target = root / "BE" / "IG_UI_BE.txt"
    old_target.write_text('A = "Target"\n', encoding="utf-8")
    delta = GitFileDelta(
        kind="renamed",
        path="EN/Renamed_EN.txt",
        previous_path="EN/IG_UI_EN.txt",
        keys=(),
    )
    change_set = GitSyncChangeSet(
        baseline="a" * 40,
        head="b" * 40,
        files=(delta,),
    )

    plan = build_merge_plan(
        root,
        change_set,
        locales=locales,
        selected_locales=["BE"],
    )

    assert len(plan.items) == 1
    assert plan.items[0].kinds == ("file_renamed",)
    assert plan.items[0].target_path == "BE/IG_UI_BE.txt"
