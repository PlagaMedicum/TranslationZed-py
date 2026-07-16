"""Read-only Git history inspection for EN synchronization."""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Literal

from .app_config import load as _load_app_config
from .atomic_io import write_text_atomic
from .translation_format import supported_extensions

GIT_SYNC_STATE_VERSION = 1
GIT_TIMEOUT_SECONDS = 30
GIT_OUTPUT_LIMIT_BYTES = 64 * 1024 * 1024
GitChangeKind = Literal["added", "modified", "deleted", "renamed"]
GitSyncStateProblem = Literal[
    "missing",
    "unreadable",
    "malformed",
    "unsupported_version",
    "invalid_baseline",
]


class GitSyncError(RuntimeError):
    """Report a read-only Git synchronization failure."""

    returncode: int | None = None


@dataclass(frozen=True, slots=True)
class GitFileChange:
    """Describe one committed EN file change between two commits."""

    kind: GitChangeKind
    path: str
    previous_path: str | None = None


@dataclass(frozen=True, slots=True)
class GitSyncInspection:
    """Describe the validated repository and EN change range."""

    repository_root: Path
    baseline: str
    head: str
    changes: tuple[GitFileChange, ...]
    dirty_en: bool
    dirty_paths: tuple[str, ...] = ()
    unsupported_paths: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class GitSyncState:
    """Persist the last fully resolved local Git commit."""

    baseline: str
    version: int = GIT_SYNC_STATE_VERSION


@dataclass(frozen=True, slots=True)
class GitSyncStateRead:
    """Return state plus an actionable reason when no state is usable."""

    state: GitSyncState | None
    problem: GitSyncStateProblem | None = None


def _state_path(project_root: Path) -> Path:
    cfg = _load_app_config(project_root)
    return project_root / cfg.cache_dir / "git_sync_state.json"


def inspect_state(project_root: Path) -> GitSyncStateRead:
    """Read synchronization state without hiding missing/corrupt-state distinctions."""
    try:
        raw = _state_path(project_root).read_text(encoding="utf-8")
    except FileNotFoundError:
        return GitSyncStateRead(None, "missing")
    except OSError:
        return GitSyncStateRead(None, "unreadable")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return GitSyncStateRead(None, "malformed")
    if not isinstance(payload, dict):
        return GitSyncStateRead(None, "malformed")
    if payload.get("version") != GIT_SYNC_STATE_VERSION:
        return GitSyncStateRead(None, "unsupported_version")
    baseline = str(payload.get("baseline") or "").strip().lower()
    if not _is_object_id(baseline):
        return GitSyncStateRead(None, "invalid_baseline")
    return GitSyncStateRead(GitSyncState(baseline=baseline))


def read_state(project_root: Path) -> GitSyncState | None:
    """Read a normalized project Git synchronization state."""
    return inspect_state(project_root).state


def write_state(project_root: Path, *, baseline: str) -> GitSyncState:
    """Atomically persist a resolved baseline commit."""
    resolved = resolve_commit(project_root, baseline)
    state = GitSyncState(baseline=resolved)
    payload = json.dumps(
        {"baseline": state.baseline, "version": state.version},
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )
    write_text_atomic(_state_path(project_root), payload + "\n")
    return state


def _is_object_id(value: str) -> bool:
    return len(value) in {40, 64} and all(ch in "0123456789abcdef" for ch in value)


def _run_git(project_root: Path, *args: str) -> bytes:
    command = ("git", "-C", str(project_root), *args)
    env = os.environ.copy()
    env.update(
        {
            "GIT_OPTIONAL_LOCKS": "0",
            "GIT_TERMINAL_PROMPT": "0",
            "LC_ALL": "C",
        }
    )
    try:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            timeout=GIT_TIMEOUT_SECONDS,
            env=env,
        )
    except FileNotFoundError as exc:
        raise GitSyncError("Git executable was not found.") from exc
    except subprocess.TimeoutExpired as exc:
        raise GitSyncError("Git inspection timed out.") from exc
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        error = GitSyncError(detail or f"Git exited with status {result.returncode}.")
        error.returncode = result.returncode
        raise error
    if len(result.stdout) > GIT_OUTPUT_LIMIT_BYTES:
        raise GitSyncError("Git output exceeds the 64 MiB safety limit.")
    return result.stdout


def repository_root(project_root: Path) -> Path:
    """Return the containing Git worktree root."""
    raw = _run_git(project_root, "rev-parse", "--show-toplevel")
    root = Path(os.fsdecode(raw).strip()).resolve()
    project = project_root.resolve()
    if project != root and root not in project.parents:
        raise GitSyncError("Project root is not inside the discovered Git worktree.")
    return root


def resolve_commit(project_root: Path, ref: str = "HEAD") -> str:
    """Resolve a user ref to one full commit object ID."""
    normalized = str(ref).strip() or "HEAD"
    raw = _run_git(
        project_root,
        "rev-parse",
        "--verify",
        "--end-of-options",
        f"{normalized}^{{commit}}",
    )
    value = raw.decode("ascii", errors="strict").strip().lower()
    if not _is_object_id(value):
        raise GitSyncError(f"Git returned an invalid commit for {normalized!r}.")
    return value


def _project_prefix(repo_root: Path, project_root: Path) -> str:
    rel = project_root.resolve().relative_to(repo_root)
    return "" if rel == Path(".") else rel.as_posix().rstrip("/") + "/"


def _normalize_en_path(raw: str, *, translation_only: bool) -> str | None:
    value = raw.replace("\\", "/")
    if (
        not value
        or value.startswith("/")
        or value.endswith("/")
        or "\0" in value
        or any(ord(char) < 32 or 0xD800 <= ord(char) <= 0xDFFF for char in value)
    ):
        return None
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts:
        return None
    if len(path.parts) < 2 or path.parts[0] != "EN":
        return None
    if translation_only and (
        path.name in {"language.txt", "credits.txt"}
        or path.suffix.lower() not in supported_extensions(".txt")
    ):
        return None
    return path.as_posix()


def _normalize_project_path(raw: str) -> str | None:
    return _normalize_en_path(raw, translation_only=True)


def _display_unsupported_path(raw: str) -> str:
    return raw.encode("utf-8", errors="backslashreplace").decode("utf-8")[:500]


def _parse_name_status(
    raw: bytes,
) -> tuple[tuple[GitFileChange, ...], tuple[str, ...]]:
    fields = raw.decode("utf-8", errors="surrogateescape").split("\0")
    out: list[GitFileChange] = []
    unsupported: list[str] = []
    idx = 0
    while idx < len(fields):
        status = fields[idx]
        idx += 1
        if not status:
            continue
        code = status[:1]
        if code in {"R", "C"}:
            if idx + 1 >= len(fields):
                raise GitSyncError("Git returned a truncated rename record.")
            old_raw, new_raw = fields[idx], fields[idx + 1]
            idx += 2
            if not old_raw or not new_raw:
                raise GitSyncError("Git returned a truncated rename record.")
            old_path = _normalize_project_path(old_raw)
            new_path = _normalize_project_path(new_raw)
            if old_path is None and old_raw.startswith("EN/"):
                unsupported.append(_display_unsupported_path(old_raw))
            if new_path is None and new_raw.startswith("EN/"):
                unsupported.append(_display_unsupported_path(new_raw))
            if new_path is not None:
                out.append(
                    GitFileChange(
                        kind="renamed" if code == "R" else "added",
                        path=new_path,
                        previous_path=old_path,
                    )
                )
            elif old_path is not None:
                out.append(GitFileChange(kind="deleted", path=old_path))
            continue
        if idx >= len(fields):
            raise GitSyncError("Git returned a truncated path record.")
        raw_path = fields[idx]
        path = _normalize_project_path(raw_path)
        idx += 1
        if not raw_path:
            raise GitSyncError("Git returned a truncated path record.")
        if path is None:
            if raw_path.startswith("EN/"):
                unsupported.append(_display_unsupported_path(raw_path))
            continue
        kind: GitChangeKind
        if code == "A":
            kind = "added"
        elif code == "D":
            kind = "deleted"
        else:
            kind = "modified"
        out.append(GitFileChange(kind=kind, path=path))
    return (
        tuple(sorted(out, key=lambda item: (item.path, item.kind))),
        tuple(sorted(set(unsupported))),
    )


def _parse_dirty_paths(raw: bytes) -> tuple[str, ...]:
    fields = raw.decode("utf-8", errors="surrogateescape").split("\0")
    out: list[str] = []
    idx = 0
    while idx < len(fields):
        field = fields[idx]
        idx += 1
        if not field:
            continue
        if len(field) < 4 or field[2] != " ":
            continue
        status = field[:2]
        path = field[3:]
        normalized = _normalize_en_path(path, translation_only=False)
        if normalized is not None:
            out.append(normalized)
        if "R" in status or "C" in status:
            idx += 1
    return tuple(sorted(set(out)))


def inspect(project_root: Path, *, baseline: str) -> GitSyncInspection:
    """Inspect committed EN changes from *baseline* through local HEAD."""
    project = project_root.resolve()
    repo = repository_root(project)
    base = resolve_commit(project, baseline)
    head = resolve_commit(project, "HEAD")
    changes_raw = _run_git(
        project,
        "diff",
        "--name-status",
        "--relative",
        "-z",
        "--find-renames",
        base,
        head,
        "--",
        "EN",
    )
    changes, unsupported = _parse_name_status(changes_raw)
    dirty_raw = _run_git(
        project,
        "status",
        "--porcelain=v1",
        "-z",
        "--untracked-files=all",
        "--",
        "EN",
    )
    dirty_paths = _parse_dirty_paths(dirty_raw)
    return GitSyncInspection(
        repository_root=repo,
        baseline=base,
        head=head,
        changes=changes,
        dirty_en=bool(dirty_raw.strip()),
        dirty_paths=dirty_paths,
        unsupported_paths=unsupported,
    )


def read_blob(project_root: Path, *, commit: str, project_path: str) -> bytes | None:
    """Read one project-relative file blob from a commit, or return None when absent."""
    project = project_root.resolve()
    repo = repository_root(project)
    prefix = _project_prefix(repo, project)
    normalized = _normalize_project_path(project_path)
    if normalized is None:
        raise GitSyncError(f"Unsafe or unsupported EN path: {project_path!r}")
    object_name = f"{resolve_commit(project, commit)}:{prefix}{normalized}"
    try:
        return _run_git(project, "show", object_name)
    except GitSyncError as exc:
        if exc.returncode == 128:
            return None
        raise


__all__ = [
    "GIT_SYNC_STATE_VERSION",
    "GitFileChange",
    "GitSyncError",
    "GitSyncInspection",
    "GitSyncState",
    "GitSyncStateRead",
    "inspect",
    "inspect_state",
    "read_blob",
    "read_state",
    "repository_root",
    "resolve_commit",
    "write_state",
]
