"""Cache-only Git synchronization application and staged-comment contracts."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from translationzed_py.core import git_sync_apply
from translationzed_py.core.git_sync import (
    inspect,
    read_state,
    resolve_commit,
    write_state,
)
from translationzed_py.core.git_sync_apply import (
    GitSyncApplyError,
    apply_pending_comments,
    apply_resolved_plan,
    preflight_pending_comments,
    read_pending_comments,
)
from translationzed_py.core.git_sync_service import (
    GitSyncItemChoice,
    build_change_set,
    build_merge_plan,
    resolve_merge_plan,
)
from translationzed_py.core.model import Entry, Status
from translationzed_py.core.parser import parse
from translationzed_py.core.project_scanner import LocaleMeta
from translationzed_py.core.status_cache import cache_path
from translationzed_py.core.status_cache import write as write_status_cache


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ("git", "-C", str(root), *args),
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _project(
    tmp_path: Path,
    *,
    base_comment: str = "-- old A",
    target_comment: str = "-- old A",
    head_comment: str = "-- new A",
    target_encoding: str = "utf-8",
    target_newline: str = "\n",
) -> tuple[Path, dict[str, LocaleMeta], str]:
    root = tmp_path / "project"
    for code in ("EN", "BE"):
        locale = root / code
        locale.mkdir(parents=True)
        charset = target_encoding if code == "BE" else "utf-8"
        (locale / "language.txt").write_text(
            f"text = {code},\ncharset = {charset},\n",
            encoding="utf-8",
        )
    (root / "EN" / "UI.txt").write_text(
        f'{base_comment}\nA = "Old source"\n', encoding="utf-8"
    )
    target = root / "BE" / "UI.txt"
    target.write_bytes(
        target_newline.join(
            (target_comment, "-- TZP:PROOFREAD", 'A = "Target value"', "")
        ).encode(target_encoding)
    )
    _git(root, "init")
    _git(root, "config", "user.email", "tests@example.invalid")
    _git(root, "config", "user.name", "Tests")
    _git(root, "add", ".")
    _git(root, "commit", "-m", "baseline")
    baseline = resolve_commit(root)
    write_state(root, baseline=baseline)
    (root / "EN" / "UI.txt").write_text(
        f'{head_comment}\nA = "New source"\n', encoding="utf-8"
    )
    _git(root, "add", "EN/UI.txt")
    _git(root, "commit", "-m", "change source and comment")
    locales = {
        code: LocaleMeta(
            code,
            root / code,
            code,
            target_encoding if code == "BE" else "utf-8",
        )
        for code in ("EN", "BE")
    }
    return root, locales, baseline


def _resolved_plan(
    root: Path,
    locales: dict[str, LocaleMeta],
    baseline: str,
    choices: dict[str, GitSyncItemChoice] | None = None,
):
    change_set = build_change_set(
        root, inspect(root, baseline=baseline), en_encoding="utf-8"
    )
    plan = build_merge_plan(
        root,
        change_set,
        locales=locales,
        selected_locales=["BE"],
    )
    return plan, resolve_merge_plan(plan, choices)


def test_apply_resolved_plan_preserves_draft_and_stages_comments(
    tmp_path: Path,
) -> None:
    """Mark review in cache, retain the draft, and defer comments to Save."""
    root, locales, baseline = _project(tmp_path)
    target = root / "BE" / "UI.txt"
    parsed = parse(target)
    entry = parsed.entries[0]
    draft = Entry(
        entry.key,
        "Draft value",
        Status.PROOFREAD,
        entry.span,
        entry.segments,
        entry.gaps,
        entry.raw,
        entry.key_hash,
    )
    write_status_cache(
        root,
        target,
        [draft],
        changed_keys={"A"},
        original_values={"A": "Target value"},
    )
    before = target.read_bytes()
    _plan, resolved = _resolved_plan(root, locales, baseline)

    result = apply_resolved_plan(root, resolved, locales=locales)

    assert result.baseline == resolve_commit(root)
    assert (result.reviewed_items, result.staged_comment_items) == (1, 1)
    assert target.read_bytes() == before
    refreshed = git_sync_apply.load_target_document(
        root, target, encoding="utf-8"
    ).rows[0]
    assert (refreshed.value, refreshed.file_value, refreshed.status) == (
        "Draft value",
        "Target value",
        Status.FOR_REVIEW,
    )
    assert read_pending_comments(root)[0].replacement == ("-- new A",)
    assert read_state(root).baseline == result.baseline  # type: ignore[union-attr]
    assert _git(root, "diff", "--cached", "--name-only") == ""


def test_pending_comments_apply_on_save_and_preserve_tzp_status(
    tmp_path: Path,
) -> None:
    """Apply staged user comments atomically while retaining program status lines."""
    root, locales, baseline = _project(tmp_path)
    target = root / "BE" / "UI.txt"
    _plan, resolved = _resolved_plan(root, locales, baseline)
    apply_resolved_plan(root, resolved, locales=locales)

    assert preflight_pending_comments(root, target, encoding="utf-8") == 1
    assert apply_pending_comments(root, target, encoding="utf-8") == 1

    assert target.read_text(encoding="utf-8") == (
        '-- new A\n-- TZP:PROOFREAD\nA = "Target value"\n'
    )
    assert read_pending_comments(root) == ()


def test_pending_comments_preserve_locale_encoding_and_crlf(tmp_path: Path) -> None:
    """Keep target encoding and line endings while replacing user comments."""
    root, locales, baseline = _project(
        tmp_path,
        base_comment="-- стары",
        target_comment="-- стары",
        head_comment="-- новы",
        target_encoding="cp1251",
        target_newline="\r\n",
    )
    target = root / "BE" / "UI.txt"
    _plan, resolved = _resolved_plan(root, locales, baseline)
    apply_resolved_plan(root, resolved, locales=locales)

    assert apply_pending_comments(root, target, encoding="cp1251") == 1
    assert target.read_bytes() == (
        '-- новы\r\n-- TZP:PROOFREAD\r\nA = "Target value"\r\n'.encode("cp1251")
    )


def test_unresolved_comment_conflict_writes_nothing(tmp_path: Path) -> None:
    """Reject unresolved choices before cache, pending state, or baseline writes."""
    root, locales, baseline = _project(tmp_path, target_comment="-- local A")
    target = root / "BE" / "UI.txt"
    state_before = (root / ".tzp" / "cache" / "git_sync_state.json").read_bytes()
    original_before = target.read_bytes()
    _plan, resolved = _resolved_plan(root, locales, baseline)

    with pytest.raises(GitSyncApplyError, match="Resolve or ignore"):
        apply_resolved_plan(root, resolved, locales=locales)

    assert target.read_bytes() == original_before
    assert (
        root / ".tzp" / "cache" / "git_sync_state.json"
    ).read_bytes() == state_before
    assert not cache_path(root, target).exists()
    assert read_pending_comments(root) == ()


def test_keep_locale_resolves_comment_conflict_without_staging(
    tmp_path: Path,
) -> None:
    """Honor an explicit keep-locale comment choice while accepting the commit."""
    root, locales, baseline = _project(tmp_path, target_comment="-- local A")
    plan, unresolved = _resolved_plan(root, locales, baseline)
    item = plan.items[0]
    resolved = resolve_merge_plan(
        plan,
        {
            item.item_id: GitSyncItemChoice(
                item_id=item.item_id,
                decision="apply",
                comment_decision="keep_locale",
                mark_for_review=False,
            )
        },
    )
    assert unresolved.advance_baseline is False

    result = apply_resolved_plan(root, resolved, locales=locales)

    assert result.staged_comment_items == 0
    assert read_pending_comments(root) == ()
    assert read_state(root).baseline == resolve_commit(root)  # type: ignore[union-attr]


def test_cache_failure_does_not_advance_baseline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Leave the saved baseline untouched when a review-cache write fails."""
    root, locales, baseline = _project(tmp_path)
    _plan, resolved = _resolved_plan(root, locales, baseline)
    monkeypatch.setattr(
        git_sync_apply,
        "write_status_cache",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("cache failed")),
    )

    with pytest.raises(OSError, match="cache failed"):
        apply_resolved_plan(root, resolved, locales=locales)

    assert read_state(root).baseline == baseline  # type: ignore[union-attr]


def test_changed_local_head_rejects_stale_preview(tmp_path: Path) -> None:
    """Reject a preview when another local commit appears before Apply."""
    root, locales, baseline = _project(tmp_path)
    target = root / "BE" / "UI.txt"
    _plan, resolved = _resolved_plan(root, locales, baseline)
    (root / "EN" / "Other.txt").write_text('B = "new"\n', encoding="utf-8")
    _git(root, "add", "EN/Other.txt")
    _git(root, "commit", "-m", "advance head")

    with pytest.raises(GitSyncApplyError, match="Local HEAD changed"):
        apply_resolved_plan(root, resolved, locales=locales)

    assert read_state(root).baseline == baseline  # type: ignore[union-attr]
    assert not cache_path(root, target).exists()
    assert read_pending_comments(root) == ()


def test_baseline_write_failure_can_retry_applied_cache_effects(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Retry idempotently when cache effects precede a failed baseline write."""
    root, locales, baseline = _project(tmp_path)
    _plan, resolved = _resolved_plan(root, locales, baseline)
    real_write_state = git_sync_apply.write_state
    monkeypatch.setattr(
        git_sync_apply,
        "write_state",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("state failed")),
    )

    with pytest.raises(OSError, match="state failed"):
        apply_resolved_plan(root, resolved, locales=locales)
    assert read_state(root).baseline == baseline  # type: ignore[union-attr]

    monkeypatch.setattr(git_sync_apply, "write_state", real_write_state)
    result = apply_resolved_plan(root, resolved, locales=locales)
    assert result.baseline == resolve_commit(root)
