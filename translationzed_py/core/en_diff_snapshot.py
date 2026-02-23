"""Persistent EN diff snapshot helpers."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path

from translationzed_py.core.app_config import load as _load_app_config

_SNAPSHOT_NAME = "en_diff_snapshot.json"


def snapshot_path(root: Path) -> Path:
    """Return snapshot file path under runtime cache directory."""
    cfg = _load_app_config(root)
    return root / cfg.cache_dir / _SNAPSHOT_NAME


def hash_text(value: str) -> str:
    """Return deterministic hash for source text values."""
    digest = hashlib.blake2b(
        value.encode("utf-8", errors="replace"),
        digest_size=16,
    ).hexdigest()
    return digest


def hash_key(key: str) -> str:
    """Return deterministic hash for entry keys."""
    digest = hashlib.blake2b(
        key.encode("utf-8", errors="replace"),
        digest_size=16,
    ).hexdigest()
    return digest


def normalize_snapshot(payload: object) -> dict[str, dict[str, str]]:
    """Normalize JSON payload to snapshot structure."""
    if not isinstance(payload, dict):
        return {}
    normalized: dict[str, dict[str, str]] = {}
    for raw_rel, raw_rows in payload.items():
        rel = str(raw_rel).strip()
        if not rel or not isinstance(raw_rows, dict):
            continue
        rows: dict[str, str] = {}
        for raw_key_hash, raw_value_hash in raw_rows.items():
            key_hash = str(raw_key_hash).strip().lower()
            value_hash = str(raw_value_hash).strip().lower()
            if not key_hash or not value_hash:
                continue
            rows[key_hash] = value_hash
        if rows:
            normalized[rel] = rows
    return normalized


def read_snapshot(root: Path) -> dict[str, dict[str, str]]:
    """Read normalized EN snapshot from cache file."""
    path = snapshot_path(root)
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return {}
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return normalize_snapshot(payload)


def write_snapshot(root: Path, snapshot: Mapping[str, Mapping[str, str]]) -> None:
    """Persist snapshot JSON deterministically."""
    path = snapshot_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    normalized = normalize_snapshot(snapshot)
    payload = json.dumps(normalized, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    path.write_text(payload + "\n", encoding="utf-8")


def build_rows(values: Mapping[str, str]) -> dict[str, str]:
    """Build snapshot rows mapping from key->source values."""
    rows: dict[str, str] = {}
    for key in sorted(values):
        rows[hash_key(key)] = hash_text(str(values[key]))
    return rows


def update_file_snapshot(root: Path, rel_file: str, values: Mapping[str, str]) -> None:
    """Update one file snapshot from current EN values."""
    rel = str(rel_file).strip()
    if not rel:
        return
    snapshot = read_snapshot(root)
    rows = build_rows(values)
    if rows:
        snapshot[rel] = rows
    else:
        snapshot.pop(rel, None)
    write_snapshot(root, snapshot)
