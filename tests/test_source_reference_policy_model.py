"""Contract tests for source-reference fallback policy model (A29-SRC-1)."""

from __future__ import annotations

from translationzed_py.core.source_reference_service import (
    SOURCE_REFERENCE_FALLBACK_EN_THEN_TARGET,
    SOURCE_REFERENCE_FALLBACK_TARGET_THEN_EN,
    build_source_reference_fallback_chain,
    dump_source_reference_fallback_presets,
    load_source_reference_fallback_presets,
    normalize_source_reference_fallback_chain,
    normalize_source_reference_fallback_policy,
    resolve_source_reference_locale,
)


def test_policy_model_normalization_contracts() -> None:
    """Verify policy and chain normalization contracts are deterministic."""
    assert (
        normalize_source_reference_fallback_policy("TARGET_THEN_EN")
        == SOURCE_REFERENCE_FALLBACK_TARGET_THEN_EN
    )
    assert (
        normalize_source_reference_fallback_policy("unknown")
        == SOURCE_REFERENCE_FALLBACK_EN_THEN_TARGET
    )
    assert normalize_source_reference_fallback_chain("en -> ru -> be") == (
        "EN",
        "RU",
        "BE",
    )
    assert normalize_source_reference_fallback_chain(["be", "ru", "BE", ""]) == (
        "BE",
        "RU",
    )


def test_policy_model_preset_dump_and_load_contract() -> None:
    """Verify preset payload roundtrip and canonical ordering."""
    payload = dump_source_reference_fallback_presets(
        {
            "ru": ("EN", "BE"),
            "be": ("RU", "EN"),
        }
    )
    assert payload == '{"BE":["RU","EN"],"RU":["EN","BE"]}'
    assert load_source_reference_fallback_presets(payload) == {
        "BE": ("RU", "EN"),
        "RU": ("EN", "BE"),
    }


def test_policy_model_preset_loader_rejects_invalid_payloads() -> None:
    """Verify invalid preset payloads fail closed."""
    assert load_source_reference_fallback_presets("") == {}
    assert load_source_reference_fallback_presets("not-json") == {}
    assert load_source_reference_fallback_presets('["EN"]') == {}


def test_policy_model_build_chain_prefers_locale_preset() -> None:
    """Verify per-locale preset extends baseline policy chain."""
    chain = build_source_reference_fallback_chain(
        target_locale="BE",
        policy=SOURCE_REFERENCE_FALLBACK_EN_THEN_TARGET,
        presets={"BE": ("RU", "EN")},
    )
    assert chain == ("RU", "EN", "BE")


def test_policy_model_build_chain_falls_back_to_policy_pair() -> None:
    """Verify baseline chain follows selected fallback policy."""
    assert build_source_reference_fallback_chain(
        target_locale="BE",
        policy=SOURCE_REFERENCE_FALLBACK_EN_THEN_TARGET,
        presets={},
    ) == ("EN", "BE")
    assert build_source_reference_fallback_chain(
        target_locale="BE",
        policy=SOURCE_REFERENCE_FALLBACK_TARGET_THEN_EN,
        presets={},
    ) == ("BE", "EN")


def test_policy_model_resolver_state_table_contract() -> None:
    """Verify requested/default/chain/sorted-available resolution order."""
    requested = resolve_source_reference_locale(
        "RU",
        available_locales=("EN", "BE", "RU"),
        default="EN",
        fallback_chain=("BE",),
        fallback_locale="EN",
    )
    assert requested.resolved_locale == "RU"
    assert requested.fallback_used is False

    default_pick = resolve_source_reference_locale(
        "KO",
        available_locales=("EN", "BE", "RU"),
        default="EN",
        fallback_chain=("RU",),
        fallback_locale="BE",
    )
    assert default_pick.resolved_locale == "EN"
    assert default_pick.fallback_used is True

    chain_pick = resolve_source_reference_locale(
        "KO",
        available_locales=("BE", "RU"),
        default="EN",
        fallback_chain=("RU", "BE"),
        fallback_locale="BE",
    )
    assert chain_pick.resolved_locale == "RU"
    assert chain_pick.fallback_used is True

    sorted_pick = resolve_source_reference_locale(
        "KO",
        available_locales=("RU", "BE"),
        default="EN",
        fallback_chain=(),
        fallback_locale="JA",
    )
    assert sorted_pick.resolved_locale == "BE"
    assert sorted_pick.fallback_used is True
