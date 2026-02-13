from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from translationzed_py.core.file_workflow import (
    FileWorkflowService,
    OpenFileCallbacks,
    SaveCurrentCallbacks,
    SaveCurrentRunPlan,
    SaveFromCacheCallbacks,
    SaveFromCacheParseError,
    apply_cache_for_write,
    apply_cache_overlay,
    build_save_current_run_plan,
)
from translationzed_py.core.model import Entry, ParsedFile, Status
from translationzed_py.core.status_cache import CacheEntry, CacheMap


@dataclass(frozen=True, slots=True)
class _Meta:
    key: str
    status: Status
    span: tuple[int, int]
    segments: tuple[int, ...]
    gaps: tuple[bytes, ...]
    raw: bool
    key_hash: int


class _IndexedEntries:
    def __init__(
        self,
        entries: list[Entry],
        metas: list[_Meta],
        by_hash16: dict[int, list[int]],
    ) -> None:
        self._entries = entries
        self._metas = metas
        self._by_hash16 = by_hash16

    def __len__(self) -> int:
        return len(self._entries)

    def __getitem__(self, index: int) -> Entry:
        return self._entries[index]

    def __setitem__(self, index: int, entry: Entry) -> None:
        self._entries[index] = entry

    def __iter__(self):
        return iter(self._entries)

    def meta_at(self, index: int) -> _Meta:
        return self._metas[index]

    def index_by_hash(self, *, bits: int = 64) -> dict[int, list[int]]:
        if bits == 16:
            return self._by_hash16
        return {}


def _entry(key: str, value: str, status: Status, key_hash: int = 1) -> Entry:
    return Entry(
        key=key,
        value=value,
        status=status,
        span=(0, 0),
        segments=(),
        gaps=(),
        raw=False,
        key_hash=key_hash,
    )


def test_apply_cache_overlay_fallback_tracks_drafts_and_conflicts() -> None:
    entries = [
        _entry("A", "file-a", Status.UNTOUCHED, key_hash=11),
        _entry("B", "file-b", Status.UNTOUCHED, key_hash=22),
    ]
    cache = CacheMap(hash_bits=64)
    cache[1] = CacheEntry(Status.TRANSLATED, "draft-a", "orig-a")
    cache[2] = CacheEntry(Status.PROOFREAD, None, None)

    result = apply_cache_overlay(
        entries,
        cache,
        hash_for_entry=lambda entry: 1 if entry.key == "A" else 2,
    )

    assert result.changed_keys == {"A"}
    assert result.baseline_by_row == {0: "file-a"}
    assert result.conflict_originals == {"A": "file-a"}
    assert result.original_values == {"A": "orig-a"}
    assert entries[0].value == "draft-a"
    assert entries[0].status == Status.TRANSLATED
    assert entries[0].key_hash == 11
    assert entries[1].status == Status.PROOFREAD


def test_apply_cache_overlay_uses_indexed_lookup_for_hash_bits() -> None:
    entries = [
        _entry("A", "file-a", Status.UNTOUCHED, key_hash=111),
        _entry("B", "file-b", Status.UNTOUCHED, key_hash=222),
    ]
    metas = [
        _Meta("A", Status.UNTOUCHED, (0, 0), (), (), False, 111),
        _Meta("B", Status.UNTOUCHED, (0, 0), (), (), False, 222),
    ]
    indexed_entries = _IndexedEntries(entries, metas, by_hash16={5: [1]})
    cache = CacheMap(hash_bits=16)
    cache[5] = CacheEntry(Status.TRANSLATED, "draft-b", "orig-b")

    result = apply_cache_overlay(
        indexed_entries,
        cache,
        hash_for_entry=lambda _entry: 0,
    )

    assert result.changed_keys == {"B"}
    assert result.baseline_by_row == {1: "file-b"}
    assert result.conflict_originals == {"B": "file-b"}
    assert indexed_entries[1].value == "draft-b"
    assert indexed_entries[1].status == Status.TRANSLATED
    assert indexed_entries[1].key_hash == 222


def test_apply_cache_for_write_returns_changed_values_and_statuses() -> None:
    entries = [
        _entry("A", "file-a", Status.UNTOUCHED, key_hash=31),
        _entry("B", "file-b", Status.PROOFREAD, key_hash=32),
    ]
    cache = CacheMap(hash_bits=64)
    cache[1] = CacheEntry(Status.FOR_REVIEW, "draft-a", "orig-a")
    cache[2] = CacheEntry(Status.TRANSLATED, None, None)

    result = apply_cache_for_write(
        entries,
        cache,
        hash_for_entry=lambda entry: 1 if entry.key == "A" else 2,
    )

    assert result.changed_values == {"A": "draft-a"}
    assert result.entries[0].status == Status.FOR_REVIEW
    assert result.entries[0].value == "file-a"
    assert result.entries[1].status == Status.TRANSLATED
    assert result.entries[1].value == "file-b"
    assert result.entries[0].key_hash == 31


def test_file_workflow_service_wraps_overlay_helpers() -> None:
    service = FileWorkflowService()
    entries = [_entry("A", "file-a", Status.UNTOUCHED, key_hash=11)]
    cache = CacheMap(hash_bits=64)
    cache[1] = CacheEntry(Status.TRANSLATED, "draft-a", "orig-a")

    overlay = service.apply_cache_overlay(
        entries,
        cache,
        hash_for_entry=lambda _entry: 1,
    )
    write_overlay = service.apply_cache_for_write(
        entries,
        cache,
        hash_for_entry=lambda _entry: 1,
    )

    assert overlay.changed_keys == {"A"}
    assert write_overlay.changed_values == {"A": "draft-a"}


def test_prepare_open_file_uses_lazy_parser_and_touches_timestamp() -> None:
    service = FileWorkflowService()
    path = Path("/tmp/a.txt")
    lazy_calls = 0
    eager_calls = 0
    touched: list[tuple[Path, int]] = []
    entries = [_entry("A", "file-a", Status.UNTOUCHED, key_hash=11)]
    parsed_lazy = ParsedFile(path, entries, b'A = "file-a"\n')
    cache = CacheMap(hash_bits=64)
    cache[1] = CacheEntry(Status.TRANSLATED, "draft-a", "orig-a")

    def parse_lazy_cb(file_path: Path, encoding: str) -> ParsedFile:
        nonlocal lazy_calls
        assert file_path == path
        assert encoding == "utf-8"
        lazy_calls += 1
        return parsed_lazy

    def parse_eager_cb(_file_path: Path, _encoding: str) -> ParsedFile:
        nonlocal eager_calls
        eager_calls += 1
        raise AssertionError("Eager parser should not be used in lazy mode")

    callbacks = OpenFileCallbacks(
        parse_eager=parse_eager_cb,
        parse_lazy=parse_lazy_cb,
        read_cache=lambda file_path: cache if file_path == path else CacheMap(),
        touch_last_opened=lambda file_path, ts: touched.append((file_path, ts)),
        now_ts=lambda: 12345,
    )

    result = service.prepare_open_file(
        path,
        "utf-8",
        use_lazy_parser=True,
        callbacks=callbacks,
        hash_for_entry=lambda entry, _cache_map: 1 if entry.key == "A" else 2,
    )

    assert lazy_calls == 1
    assert eager_calls == 0
    assert touched == [(path, 12345)]
    assert result.parsed_file is parsed_lazy
    assert result.overlay.changed_keys == {"A"}
    assert result.overlay.baseline_by_row == {0: "file-a"}
    assert result.overlay.original_values == {"A": "orig-a"}


def test_build_save_current_run_plan() -> None:
    blocked = build_save_current_run_plan(
        has_current_file=True,
        has_current_model=True,
        conflicts_resolved=False,
        has_changed_keys=True,
    )
    assert blocked == SaveCurrentRunPlan(run_save=False, immediate_result=False)

    no_file = build_save_current_run_plan(
        has_current_file=False,
        has_current_model=True,
        conflicts_resolved=True,
        has_changed_keys=True,
    )
    assert no_file == SaveCurrentRunPlan(run_save=False, immediate_result=True)

    no_changes = build_save_current_run_plan(
        has_current_file=True,
        has_current_model=True,
        conflicts_resolved=True,
        has_changed_keys=False,
    )
    assert no_changes == SaveCurrentRunPlan(run_save=False, immediate_result=True)

    run = build_save_current_run_plan(
        has_current_file=True,
        has_current_model=True,
        conflicts_resolved=True,
        has_changed_keys=True,
    )
    assert run == SaveCurrentRunPlan(run_save=True, immediate_result=None)


def test_persist_current_save_writes_original_and_cache() -> None:
    service = FileWorkflowService()
    path = Path("/tmp/a.txt")
    parsed = ParsedFile(path, [_entry("A", "a", Status.UNTOUCHED)], b'A = "a"\n')
    saved_payload: list[tuple[dict[str, str], str]] = []
    cache_payload: list[tuple[Path, int]] = []
    callbacks = SaveCurrentCallbacks(
        save_file=lambda _pf, changed, enc: saved_payload.append((dict(changed), enc)),
        write_cache=lambda write_path, _entries, ts: cache_payload.append(
            (write_path, ts)
        ),
        now_ts=lambda: 777,
    )

    result = service.persist_current_save(
        path=path,
        parsed_file=parsed,
        changed_values={"A": "b"},
        encoding="utf-8",
        callbacks=callbacks,
    )

    assert result.wrote_original is True
    assert result.wrote_cache is True
    assert saved_payload == [({"A": "b"}, "utf-8")]
    assert cache_payload == [(path, 777)]


def test_persist_current_save_with_no_changes_still_writes_cache() -> None:
    service = FileWorkflowService()
    path = Path("/tmp/a.txt")
    parsed = ParsedFile(path, [_entry("A", "a", Status.UNTOUCHED)], b'A = "a"\n')
    saved_calls = 0
    cache_calls = 0

    def _save_file(_pf, _changed, _enc):  # type: ignore[no-untyped-def]
        nonlocal saved_calls
        saved_calls += 1

    def _write_cache(_path, _entries, _ts):  # type: ignore[no-untyped-def]
        nonlocal cache_calls
        cache_calls += 1

    callbacks = SaveCurrentCallbacks(
        save_file=_save_file,
        write_cache=_write_cache,
        now_ts=lambda: 101,
    )
    result = service.persist_current_save(
        path=path,
        parsed_file=parsed,
        changed_values={},
        encoding="utf-8",
        callbacks=callbacks,
    )
    assert result.wrote_original is False
    assert result.wrote_cache is True
    assert saved_calls == 0
    assert cache_calls == 1


def test_file_workflow_service_wraps_save_current_helpers() -> None:
    service = FileWorkflowService()
    run_plan = service.build_save_current_run_plan(
        has_current_file=True,
        has_current_model=True,
        conflicts_resolved=True,
        has_changed_keys=True,
    )
    assert run_plan.run_save is True


def test_write_from_cache_skips_when_no_draft_values() -> None:
    service = FileWorkflowService()
    path = Path("/tmp/a.txt")
    cache = CacheMap(hash_bits=64)
    cache[1] = CacheEntry(Status.TRANSLATED, None, None)
    parsed_calls = 0
    save_calls = 0
    write_cache_calls = 0

    callbacks = SaveFromCacheCallbacks(
        parse_file=lambda _path, _enc: (_ for _ in ()).throw(
            AssertionError("parse should not run")
        ),
        save_file=lambda _pf, _vals, _enc: (_ for _ in ()).throw(
            AssertionError("save should not run")
        ),
        write_cache=lambda _path, _entries: (_ for _ in ()).throw(
            AssertionError("write_cache should not run")
        ),
    )

    result = service.write_from_cache(
        path,
        "utf-8",
        cache_map=cache,
        callbacks=callbacks,
        hash_for_entry=lambda _entry: 1,
    )

    assert parsed_calls == 0
    assert save_calls == 0
    assert write_cache_calls == 0
    assert result.had_drafts is False
    assert result.wrote_original is False
    assert result.changed_values == {}


def test_write_from_cache_applies_overlay_and_writes_cache() -> None:
    service = FileWorkflowService()
    path = Path("/tmp/a.txt")
    entries = [_entry("A", "file-a", Status.UNTOUCHED, key_hash=31)]
    parsed = ParsedFile(path, entries, b'A = "file-a"\n')
    cache = CacheMap(hash_bits=64)
    cache[1] = CacheEntry(Status.FOR_REVIEW, "draft-a", "orig-a")
    saved_payload: list[tuple[dict[str, str], str]] = []
    cache_written: list[list[Entry]] = []

    callbacks = SaveFromCacheCallbacks(
        parse_file=lambda file_path, _enc: parsed if file_path == path else parsed,
        save_file=lambda _pf, vals, enc: saved_payload.append((dict(vals), enc)),
        write_cache=lambda _path, write_entries: cache_written.append(
            list(write_entries)
        ),
    )

    result = service.write_from_cache(
        path,
        "utf-8",
        cache_map=cache,
        callbacks=callbacks,
        hash_for_entry=lambda _entry: 1,
    )

    assert result.had_drafts is True
    assert result.wrote_original is True
    assert dict(result.changed_values) == {"A": "draft-a"}
    assert saved_payload == [({"A": "draft-a"}, "utf-8")]
    assert len(cache_written) == 1
    assert cache_written[0][0].status == Status.FOR_REVIEW


def test_write_from_cache_wraps_parse_errors() -> None:
    service = FileWorkflowService()
    path = Path("/tmp/a.txt")
    cache = CacheMap(hash_bits=64)
    cache[1] = CacheEntry(Status.TRANSLATED, "draft-a", "orig-a")
    callbacks = SaveFromCacheCallbacks(
        parse_file=lambda _path, _enc: (_ for _ in ()).throw(
            ValueError("parse-failed")
        ),
        save_file=lambda _pf, _vals, _enc: None,
        write_cache=lambda _path, _entries: None,
    )

    try:
        service.write_from_cache(
            path,
            "utf-8",
            cache_map=cache,
            callbacks=callbacks,
            hash_for_entry=lambda _entry: 1,
        )
    except SaveFromCacheParseError as exc:
        assert exc.path == path
        assert isinstance(exc.original, ValueError)
        assert str(exc.original) == "parse-failed"
    else:
        raise AssertionError("SaveFromCacheParseError expected")
