from pathlib import Path

from translationzed_py.gui.source_reference_state import (
    apply_source_reference_mode_change,
    apply_source_reference_preferences,
    normalize_source_reference_fallback_policy,
    source_reference_fallback_pair,
)


def test_apply_source_reference_mode_change_updates_global_mode() -> None:
    extras: dict[str, str] = {}
    overrides: dict[str, str] = {}
    mode, changed = apply_source_reference_mode_change(
        mode="RU",
        root=Path("/tmp/proj"),
        current_path=Path("/tmp/proj/BE/ui.txt"),
        default_mode="EN",
        overrides=overrides,
        extras=extras,
    )
    assert changed is True
    assert mode == "RU"
    assert extras["SOURCE_REFERENCE_MODE"] == "RU"


def test_apply_source_reference_mode_change_updates_file_override() -> None:
    extras: dict[str, str] = {}
    overrides = {"BE/ui.txt": "EN"}
    mode, changed = apply_source_reference_mode_change(
        mode="RU",
        root=Path("/tmp/proj"),
        current_path=Path("/tmp/proj/BE/ui.txt"),
        default_mode="EN",
        overrides=overrides,
        extras=extras,
    )
    assert changed is True
    assert mode == "RU"
    assert overrides == {"BE/ui.txt": "EN"}
    assert "SOURCE_REFERENCE_FILE_OVERRIDES" not in extras


def test_normalize_source_reference_fallback_policy() -> None:
    assert (
        normalize_source_reference_fallback_policy("target_then_en") == "TARGET_THEN_EN"
    )
    assert normalize_source_reference_fallback_policy("bad") == "EN_THEN_TARGET"


def test_source_reference_fallback_pair() -> None:
    assert source_reference_fallback_pair("BE", "EN_THEN_TARGET") == ("EN", "BE")
    assert source_reference_fallback_pair("BE", "TARGET_THEN_EN") == ("BE", "EN")


def test_apply_source_reference_preferences_updates_policy() -> None:
    extras: dict[str, str] = {}
    overrides = {"BE/ui.txt": "RU"}
    policy, changed = apply_source_reference_preferences(
        values={"source_reference_fallback_policy": "TARGET_THEN_EN"},
        current_fallback_policy="EN_THEN_TARGET",
        overrides=overrides,
        extras=extras,
    )
    assert changed is True
    assert policy == "TARGET_THEN_EN"
    assert overrides == {"BE/ui.txt": "RU"}
    assert extras["SOURCE_REFERENCE_FALLBACK_POLICY"] == "TARGET_THEN_EN"
