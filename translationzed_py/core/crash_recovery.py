from __future__ import annotations

import json
import tempfile
import time
from pathlib import Path

from translationzed_py.core.app_config import load as _load_app_config
from translationzed_py.core.atomic_io import write_text_atomic

_RECOVERY_FILE = "tzpy_recovery.json"
_VERSION = 1


def recovery_path() -> Path:
    return Path(tempfile.gettempdir()) / _RECOVERY_FILE


def write(root: Path, files: list[Path]) -> None:
    path = recovery_path()
    rel_files: list[str] = []
    root_resolved = root.resolve()
    for file_path in files:
        try:
            rel = Path(file_path).resolve().relative_to(root_resolved)
        except Exception:
            continue
        rel_files.append(rel.as_posix())
    if not rel_files:
        if path.exists():
            path.unlink()
        return
    payload = {
        "version": _VERSION,
        "root": str(root_resolved),
        "files": sorted(set(rel_files)),
        "timestamp": int(time.time()),
    }
    write_text_atomic(path, json.dumps(payload, indent=2, sort_keys=True))


def read() -> dict[str, object] | None:
    path = recovery_path()
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    if data.get("version") != _VERSION:
        return None
    root = data.get("root")
    files = data.get("files")
    if not isinstance(root, str) or not isinstance(files, list):
        return None
    rel_files = [str(item) for item in files if isinstance(item, str)]
    return {
        "root": root,
        "files": rel_files,
        "timestamp": data.get("timestamp"),
    }


def clear() -> None:
    path = recovery_path()
    if path.exists():
        path.unlink()


def discard_cache(root: Path, rel_files: list[str]) -> None:
    cfg = _load_app_config(root)
    cache_root = root / cfg.cache_dir
    for rel in rel_files:
        rel_path = Path(rel)
        cache_path = (cache_root / rel_path).with_suffix(cfg.cache_ext)
        try:
            cache_path.unlink()
        except FileNotFoundError:
            continue
        _prune_empty_dirs(cache_path.parent, cache_root)


def _prune_empty_dirs(path: Path, stop: Path) -> None:
    current = path
    while current != stop and current.exists():
        try:
            current.rmdir()
        except OSError:
            break
        current = current.parent
