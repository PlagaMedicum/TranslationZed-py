"""Test module for EN diff snapshot helpers."""

from __future__ import annotations

import json
from pathlib import Path

from translationzed_py.core import en_diff_snapshot


def test_snapshot_roundtrip_and_update_file(tmp_path: Path) -> None:
    """Verify snapshot read/write and file-level update are deterministic."""
    root = tmp_path
    en_diff_snapshot.write_snapshot(
        root,
        {
            "EN/ui.txt": {"a": "1"},
            "EN/other.txt": {"b": "2"},
        },
    )
    loaded = en_diff_snapshot.read_snapshot(root)
    assert loaded["EN/ui.txt"]["a"] == "1"
    assert loaded["EN/other.txt"]["b"] == "2"

    en_diff_snapshot.update_file_snapshot(
        root,
        "EN/ui.txt",
        {"UI_OK": "OK", "UI_CANCEL": "Cancel"},
    )
    updated = en_diff_snapshot.read_snapshot(root)
    assert "EN/ui.txt" in updated
    assert len(updated["EN/ui.txt"]) == 2
    assert "EN/other.txt" in updated


def test_snapshot_read_handles_malformed_payload(tmp_path: Path) -> None:
    """Verify malformed JSON payload is treated as empty snapshot."""
    path = en_diff_snapshot.snapshot_path(tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{invalid", encoding="utf-8")
    assert en_diff_snapshot.read_snapshot(tmp_path) == {}


def test_normalize_snapshot_filters_invalid_rows() -> None:
    """Verify normalization drops invalid file and row entries."""
    normalized = en_diff_snapshot.normalize_snapshot(
        {
            "EN/ui.txt": {"A": "B", "": "x"},
            "": {"c": "d"},
            "EN/empty.txt": {},
            "EN/invalid.txt": "x",
        }
    )
    assert normalized == {"EN/ui.txt": {"a": "b"}}


def test_build_rows_hashes_keys_and_values_stably() -> None:
    """Verify build rows returns key/value hashes for all entries."""
    rows = en_diff_snapshot.build_rows({"B": "2", "A": "1"})
    assert len(rows) == 2
    key_hash = en_diff_snapshot.hash_key("A")
    assert key_hash in rows
    assert rows[key_hash] == en_diff_snapshot.hash_text("1")


def test_write_snapshot_produces_json_object(tmp_path: Path) -> None:
    """Verify persisted snapshot file contains compact JSON mapping."""
    en_diff_snapshot.write_snapshot(tmp_path, {"EN/ui.txt": {"a": "1"}})
    path = en_diff_snapshot.snapshot_path(tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload == {"EN/ui.txt": {"a": "1"}}
