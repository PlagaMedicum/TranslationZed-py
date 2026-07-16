"""Tests for read-only Git-backed EN change inspection."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from translationzed_py.core import git_sync
from translationzed_py.core.git_sync import (
    GitSyncError,
    inspect,
    read_blob,
    read_state,
    resolve_commit,
    write_state,
)


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ("git", "-C", str(root), *args),
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _repo(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    (root / "EN").mkdir(parents=True)
    _git(root, "init")
    _git(root, "config", "user.email", "tests@example.invalid")
    _git(root, "config", "user.name", "Tests")
    (root / "EN" / "language.txt").write_text(
        "text = English\ncharset = UTF-8\n", encoding="utf-8"
    )
    (root / "EN" / "ui.txt").write_text('A = "old"\n', encoding="utf-8")
    (root / "EN" / "rename.txt").write_text('R = "rename"\n', encoding="utf-8")
    (root / "EN" / "delete.txt").write_text('D = "delete"\n', encoding="utf-8")
    _git(root, "add", ".")
    _git(root, "commit", "-m", "baseline")
    return root


def test_inspect_committed_en_changes_and_read_blobs(tmp_path: Path) -> None:
    """Inspect committed EN changes and return exact historical blobs."""
    root = _repo(tmp_path)
    baseline = resolve_commit(root)
    (root / "EN" / "ui.txt").write_text('A = "new"\n', encoding="utf-8")
    (root / "EN" / "new.txt").write_text('B = "new"\n', encoding="utf-8")
    _git(root, "mv", "EN/rename.txt", "EN/renamed.txt")
    (root / "EN" / "delete.txt").unlink()
    _git(root, "add", ".")
    _git(root, "commit", "-m", "change EN")

    result = inspect(root, baseline=baseline)

    assert result.baseline == baseline
    assert result.head == resolve_commit(root)
    assert [(item.kind, item.path) for item in result.changes] == [
        ("deleted", "EN/delete.txt"),
        ("added", "EN/new.txt"),
        ("renamed", "EN/renamed.txt"),
        ("modified", "EN/ui.txt"),
    ]
    assert result.changes[2].previous_path == "EN/rename.txt"
    assert read_blob(root, commit=baseline, project_path="EN/ui.txt") == b'A = "old"\n'
    assert (
        read_blob(root, commit=result.head, project_path="EN/new.txt") == b'B = "new"\n'
    )


def test_inspect_reports_dirty_en_without_including_worktree_diff(
    tmp_path: Path,
) -> None:
    """Report dirty EN files without treating them as committed changes."""
    root = _repo(tmp_path)
    baseline = resolve_commit(root)
    (root / "EN" / "ui.txt").write_text('A = "dirty"\n', encoding="utf-8")

    result = inspect(root, baseline=baseline)

    assert result.changes == ()
    assert result.dirty_en is True


def test_inspect_and_read_blob_preserve_b42_json_format_identity(
    tmp_path: Path,
) -> None:
    """Committed JSON paths remain distinct and readable across the Git boundary."""
    root = _repo(tmp_path)
    path = root / "EN" / "UI.json"
    path.write_text('{"A": "old"}', encoding="utf-8")
    _git(root, "add", "EN/UI.json")
    _git(root, "commit", "-m", "add B42 source")
    baseline = resolve_commit(root)
    path.write_text('{"A": "new"}', encoding="utf-8")
    _git(root, "add", "EN/UI.json")
    _git(root, "commit", "-m", "change B42 source")

    result = inspect(root, baseline=baseline)

    assert [(item.kind, item.path) for item in result.changes] == [
        ("modified", "EN/UI.json")
    ]
    assert (
        read_blob(root, commit=baseline, project_path="EN/UI.json") == b'{"A": "old"}'
    )


def test_inspect_reports_untracked_en_as_dirty(tmp_path: Path) -> None:
    """Warn about untracked EN files without treating them as committed changes."""
    root = _repo(tmp_path)
    baseline = resolve_commit(root)
    (root / "EN" / "untracked.txt").write_text('A = "new"\n', encoding="utf-8")

    result = inspect(root, baseline=baseline)

    assert result.changes == ()
    assert result.dirty_en is True


def test_state_roundtrip_is_versioned_and_resolved(tmp_path: Path) -> None:
    """Persist a versioned state containing a resolved commit ID."""
    root = _repo(tmp_path)

    written = write_state(root, baseline="HEAD")

    assert written.baseline == resolve_commit(root)
    assert read_state(root) == written


@pytest.mark.parametrize(
    "payload",
    ["{", "[]", '{"version": 2, "baseline": "0"}', '{"version": 1, "baseline": "bad"}'],
)
def test_read_state_ignores_invalid_payloads(tmp_path: Path, payload: str) -> None:
    """Ignore malformed, obsolete, and invalid synchronization state."""
    state_path = tmp_path / ".tzp" / "cache" / "git_sync_state.json"
    state_path.parent.mkdir(parents=True)
    state_path.write_text(payload, encoding="utf-8")

    assert read_state(tmp_path) is None


@pytest.mark.parametrize(
    ("failure", "message"),
    [
        (FileNotFoundError(), "not found"),
        (subprocess.TimeoutExpired("git", 30), "timed out"),
    ],
)
def test_git_process_failures_are_actionable(
    tmp_path: Path, monkeypatch, failure: Exception, message: str
) -> None:
    """Normalize missing-executable and timeout failures."""

    def fail(*_args, **_kwargs):
        raise failure

    monkeypatch.setattr(git_sync.subprocess, "run", fail)

    with pytest.raises(GitSyncError, match=message):
        resolve_commit(tmp_path)


def test_read_blob_rejects_non_en_and_traversal_paths(tmp_path: Path) -> None:
    """Reject traversal and paths outside the supported EN tree."""
    root = _repo(tmp_path)

    for path in ("../secret.txt", "/EN/ui.txt", "RU/ui.txt"):
        with pytest.raises(GitSyncError, match="Unsafe or unsupported"):
            read_blob(root, commit="HEAD", project_path=path)


def test_read_blob_returns_none_for_missing_commit_path(tmp_path: Path) -> None:
    """Treat an absent safe path as a normal historical deletion."""
    root = _repo(tmp_path)

    assert read_blob(root, commit="HEAD", project_path="EN/missing.txt") is None


def test_inspect_supports_project_nested_inside_repository(tmp_path: Path) -> None:
    """Keep reported paths project-relative for a nested translation root."""
    repo = tmp_path / "repo"
    project = repo / "translations"
    (project / "EN").mkdir(parents=True)
    _git(repo, "init")
    _git(repo, "config", "user.email", "tests@example.invalid")
    _git(repo, "config", "user.name", "Tests")
    path = project / "EN" / "ui.txt"
    path.write_text('A = "old"\n', encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "baseline")
    baseline = resolve_commit(project)
    path.write_text('A = "new"\n', encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "change")

    result = inspect(project, baseline=baseline)

    assert result.repository_root == repo.resolve()
    assert result.changes[0].path == "EN/ui.txt"
