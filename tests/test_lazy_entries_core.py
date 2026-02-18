"""Test module for lazy entries core behavior."""

from __future__ import annotations

import codecs

from translationzed_py.core.lazy_entries import EntryMeta, LazyEntries
from translationzed_py.core.model import Entry, Status


def _build_lazy_entries_sample() -> LazyEntries:
    """Provide a mixed lazy-entries sample with literal, plain, and raw values."""
    raw = b'"Hel".."lo"|plain text|Raw body'
    quoted_a = (0, 5)
    quoted_b = (7, 11)
    plain_start = raw.index(b"plain text")
    plain_end = plain_start + len(b"plain text")
    raw_start = raw.index(b"Raw body")
    raw_end = raw_start + len(b"Raw body")

    metas = [
        EntryMeta(
            key="HELLO",
            status=Status.UNTOUCHED,
            span=(quoted_a[0], quoted_b[1]),
            segments=(3, 2),
            gaps=(b"..",),
            raw=False,
            seg_spans=(quoted_a, quoted_b),
            key_hash=0x12340001,
        ),
        EntryMeta(
            key="PLAIN",
            status=Status.TRANSLATED,
            span=(plain_start, plain_end),
            segments=(10,),
            gaps=(),
            raw=False,
            seg_spans=((plain_start, plain_end),),
            key_hash=0x56780001,
        ),
        EntryMeta(
            key="RAW",
            status=Status.FOR_REVIEW,
            span=(raw_start, raw_end),
            segments=(8,),
            gaps=(),
            raw=True,
            seg_spans=((raw_start, raw_end),),
            key_hash=0xABCDEF02,
        ),
    ]
    return LazyEntries(raw=raw, encoding="utf-8", metas=metas)


def test_lazy_entries_len_meta_and_key_accessors() -> None:
    """Verify lazy entries expose stable size and metadata lookups."""
    entries = _build_lazy_entries_sample()
    assert len(entries) == 3
    assert entries.meta_at(1).key == "PLAIN"
    assert entries.key_at(2) == "RAW"


def test_lazy_entries_getitem_and_iter_resolve_values() -> None:
    """Verify lazy entries decode values for indexed and iterative access."""
    entries = _build_lazy_entries_sample()
    assert entries[0].value == "Hello"
    assert entries[1].value == "plain text"
    assert entries[2].value == '"Hel".."lo"|plain text|Raw body'
    assert [entry.value for entry in entries] == [
        "Hello",
        "plain text",
        '"Hel".."lo"|plain text|Raw body',
    ]


def test_lazy_entries_setitem_overrides_value_lookup() -> None:
    """Verify lazy entries return explicit override entries."""
    entries = _build_lazy_entries_sample()
    override = Entry(
        key="PLAIN",
        value="patched",
        status=Status.PROOFREAD,
        span=entries.meta_at(1).span,
        segments=(7,),
        gaps=(),
        raw=False,
        key_hash=entries.meta_at(1).key_hash,
    )
    entries[1] = override
    assert entries[1] == override


def test_lazy_entries_prefetch_populates_cache_with_bounds_clamp() -> None:
    """Verify lazy entries prefetch fills uncached values within safe bounds."""
    entries = _build_lazy_entries_sample()
    entries.prefetch(-3, 99)
    assert entries._value_cache[0] == "Hello"
    assert entries._value_cache[1] == "plain text"
    assert entries._value_cache[2].endswith("Raw body")


def test_lazy_entries_max_value_length_uses_segment_totals() -> None:
    """Verify lazy entries max length tracks longest segment sum."""
    entries = _build_lazy_entries_sample()
    assert entries.max_value_length() == 10
    assert entries.max_value_length() == 10


def test_lazy_entries_preview_handles_literal_plain_and_raw_modes() -> None:
    """Verify lazy entries preview respects limits across entry modes."""
    entries = _build_lazy_entries_sample()
    assert entries.preview_at(0, 4) == "Hell"
    assert entries.preview_at(1, 5) == "plain"
    assert entries.preview_at(1, 3) == "pla"
    assert entries.preview_at(2, 4) == '"Hel'
    assert entries.preview_at(0, 0) == ""


def test_lazy_entries_index_by_hash_supports_64_and_16_bit_indexes() -> None:
    """Verify lazy entries build stable hash indexes for both key widths."""
    entries = _build_lazy_entries_sample()
    idx64 = entries.index_by_hash(bits=64)
    idx16 = entries.index_by_hash(bits=16)

    assert idx64[0x12340001] == [0]
    assert idx64[0x56780001] == [1]
    assert idx16[0x0001] == [0, 1]
    assert idx16[0xEF02] == [2]
    assert entries.index_by_hash(bits=16) is idx16
    assert entries.index_by_hash(bits=64) is idx64


def test_lazy_entries_decode_prefix_guards_empty_inputs() -> None:
    """Verify lazy entries decode prefix short-circuits empty requests."""
    entries = _build_lazy_entries_sample()
    assert entries._decode_prefix(b"", 5) == ""
    assert entries._decode_prefix(b"abcdef", 0) == ""


def test_lazy_entries_strip_bom_for_quoted_and_raw_previews() -> None:
    """Verify lazy entries drop BOM for value and preview generation."""
    raw_quoted = codecs.BOM_UTF8 + b'"Hi"'
    quoted_meta = EntryMeta(
        key="BOM_Q",
        status=Status.UNTOUCHED,
        span=(0, len(raw_quoted)),
        segments=(2,),
        gaps=(),
        raw=False,
        seg_spans=((0, len(raw_quoted)),),
        key_hash=1,
    )
    quoted_entries = LazyEntries(raw=raw_quoted, encoding="utf-8", metas=[quoted_meta])
    assert quoted_entries[0].value == "Hi"
    assert quoted_entries.preview_at(0, 2) == "Hi"

    raw_plain = codecs.BOM_UTF8 + b"Body"
    raw_meta = EntryMeta(
        key="BOM_RAW",
        status=Status.UNTOUCHED,
        span=(0, len(raw_plain)),
        segments=(4,),
        gaps=(),
        raw=True,
        seg_spans=((0, len(raw_plain)),),
        key_hash=2,
    )
    raw_entries = LazyEntries(raw=raw_plain, encoding="utf-8", metas=[raw_meta])
    assert raw_entries[0].value == "Body"
    assert raw_entries.preview_at(0, 3) == "Bod"
