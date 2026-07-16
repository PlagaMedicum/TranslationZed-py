"""Read-only Git history inspection for EN synchronization."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Literal

from .app_config import load as _load_app_config
from .atomic_io import write_text_atomic
from .translation_format import supported_extensions

GIT_SYNC_STATE_VERSION = 1
GitChangeKind = Literal["added", "modified", "deleted", "renamed"]


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


@dataclass(frozen=True, slots=True)
class GitSyncState:
    """Persist the last fully resolved local Git commit."""

    baseline: str
    version: int = GIT_SYNC_STATE_VERSION


def _state_path(project_root: Path) -> Path:
    cfg = _load_app_config(project_root)
    return project_root / cfg.cache_dir / "git_sync_state.json"


def read_state(project_root: Path) -> GitSyncState | None:
    """Read a normalized project Git synchronization state."""
    try:
        payload = json.loads(_state_path(project_root).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if (
        not isinstance(payload, dict)
        or payload.get("version") != GIT_SYNC_STATE_VERSION
    ):
        return None
    baseline = str(payload.get("baseline") or "").strip().lower()
    if len(baseline) != 40 or any(ch not in "0123456789abcdef" for ch in baseline):
        return None
    return GitSyncState(baseline=baseline)


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


def _run_git(project_root: Path, *args: str) -> bytes:
    command = ("git", "-C", str(project_root), *args)
    try:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            timeout=30,
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
    return result.stdout


def repository_root(project_root: Path) -> Path:
    """Return the containing Git worktree root."""
    raw = _run_git(project_root, "rev-parse", "--show-toplevel")
    root = Path(raw.decode("utf-8", errors="strict").strip()).resolve()
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
    if len(value) != 40:
        raise GitSyncError(f"Git returned an invalid commit for {normalized!r}.")
    return value


def _project_prefix(repo_root: Path, project_root: Path) -> str:
    rel = project_root.resolve().relative_to(repo_root)
    return "" if rel == Path(".") else rel.as_posix().rstrip("/") + "/"


def _normalize_project_path(raw: str) -> str | None:
    value = raw.replace("\\", "/")
    if not value or value.startswith("/") or value.endswith("/") or "\0" in value:
        return None
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts:
        return None
    if len(path.parts) < 2 or path.parts[0] != "EN":
        return None
    if path.name in {
        "language.txt",
        "credits.txt",
    } or path.suffix.lower() not in supported_extensions(".txt"):
        return None
    return path.as_posix()


def _parse_name_status(raw: bytes) -> tuple[GitFileChange, ...]:
    fields = raw.decode("utf-8", errors="surrogateescape").split("\0")
    out: list[GitFileChange] = []
    idx = 0
    while idx < len(fields):
        status = fields[idx]
        idx += 1
        if not status:
            continue
        code = status[:1]
        if code in {"R", "C"}:
            if idx + 1 >= len(fields):
                break
            old_raw, new_raw = fields[idx], fields[idx + 1]
            idx += 2
            old_path = _normalize_project_path(old_raw)
            new_path = _normalize_project_path(new_raw)
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
            break
        path = _normalize_project_path(fields[idx])
        idx += 1
        if path is None:
            continue
        kind: GitChangeKind
        if code == "A":
            kind = "added"
        elif code == "D":
            kind = "deleted"
        else:
            kind = "modified"
        out.append(GitFileChange(kind=kind, path=path))
    return tuple(sorted(out, key=lambda item: (item.path, item.kind)))


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
    dirty = bool(
        _run_git(
            project,
            "status",
            "--porcelain",
            "--untracked-files=all",
            "--",
            "EN",
        ).strip()
    )
    return GitSyncInspection(
        repository_root=repo,
        baseline=base,
        head=head,
        changes=_parse_name_status(changes_raw),
        dirty_en=dirty,
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
    "inspect",
    "read_blob",
    "read_state",
    "repository_root",
    "resolve_commit",
    "write_state",
]
