"""Test module for EN insertion plan helpers."""

from __future__ import annotations

from translationzed_py.core.en_insert_plan import (
    ENInsertPlan,
    apply_insert_plan,
    build_insert_plan,
)


def test_build_insert_plan_preserves_en_order_and_anchor_selection() -> None:
    """Verify insert plan follows EN key order and resolves insertion anchors."""
    en_text = 'key1 = "A"\n' 'key1_2 = "B"\n' "# note\n" 'key2 = "C"\n' 'key3 = "D"\n'
    locale_text = 'key1 = "AA"\nkey2 = "CC"\n'
    plan = build_insert_plan(
        en_text=en_text,
        locale_text=locale_text,
        edited_new_values={"key3": "XX", "key1_2": "YY"},
    )
    assert [item.key for item in plan.items] == ["key1_2", "key3"]
    assert plan.items[0].anchor_key == "key1"
    assert plan.items[1].anchor_key == "key2"
    assert plan.items[0].snippet_lines[-1] == "# note"


def test_build_insert_plan_deduplicates_adjacent_comment_blocks() -> None:
    """Verify shared trailing/leading comments are not duplicated across inserted items."""
    en_text = 'A = "a"\n' "# shared\n" 'B = "b"\n' "# shared\n" 'C = "c"\n'
    locale_text = 'A = "a"\n'
    plan = build_insert_plan(
        en_text=en_text,
        locale_text=locale_text,
        edited_new_values={"B": "bb", "C": "cc"},
    )
    assert len(plan.items) == 2
    first = plan.items[0].snippet_lines
    second = plan.items[1].snippet_lines
    assert first[-1] == "# shared"
    assert second[0] != "# shared"


def test_apply_insert_plan_merges_lines_and_supports_manual_edits() -> None:
    """Verify apply inserts snippets at anchor and accepts edited snippet overrides."""
    locale = 'K1 = "one"\nK3 = "three"\n'
    plan = ENInsertPlan(
        items=(
            build_insert_plan(
                en_text='K1 = "one"\nK2 = "two"\nK3 = "three"\n',
                locale_text=locale,
                edited_new_values={"K2": "two-local"},
            ).items[0],
        )
    )
    merged = apply_insert_plan(locale_text=locale, plan=plan)
    assert 'K2 = "two-local"' in merged
    assert merged.index('K2 = "two-local"') > merged.index('K1 = "one"')

    edited = apply_insert_plan(
        locale_text=locale,
        plan=plan,
        edited_snippets={"K2": '# custom\nK2 = "manual"\n'},
    )
    assert '# custom\nK2 = "manual"' in edited
