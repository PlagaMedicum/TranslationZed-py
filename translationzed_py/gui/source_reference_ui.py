"""UI helpers for direct source-reference selection widgets."""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from PySide6.QtWidgets import QComboBox

from translationzed_py.core.source_reference_service import (
    normalize_source_reference_mode,
)


def _normalize_locales(locales: Iterable[str]) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for locale in locales:
        code = str(locale).strip().upper()
        if not code or code in seen:
            continue
        seen.add(code)
        ordered.append(code)
    return ordered


def available_source_reference_locales(
    selected_locales: Sequence[str],
    *,
    all_locales: Iterable[str] | None = None,
) -> list[str]:
    """Return ordered source-reference locale options for UI selection."""
    selected = _normalize_locales(selected_locales)
    all_codes = _normalize_locales(all_locales or selected)
    merged = ["EN"]
    seen = {"EN"}
    for locale in selected:
        if locale == "EN" or locale in seen:
            continue
        seen.add(locale)
        merged.append(locale)
    for locale in all_codes:
        if locale == "EN" or locale in seen:
            continue
        seen.add(locale)
        merged.append(locale)
    return merged


def sync_source_reference_combo(
    combo: QComboBox,
    *,
    current_mode: str,
    selected_locales: Sequence[str],
    all_locales: Iterable[str] | None = None,
) -> str:
    """Populate the combo and keep a direct source-reference selection valid."""
    available = available_source_reference_locales(
        selected_locales,
        all_locales=all_locales,
    )
    requested = normalize_source_reference_mode(current_mode, default="EN")
    if requested in available:
        resolved = requested
    elif "EN" in available:
        resolved = "EN"
    elif available:
        resolved = available[0]
    else:
        resolved = "EN"
    blocker = combo.blockSignals(True)
    combo.clear()
    for locale in available:
        combo.addItem(locale, locale)
    idx = combo.findData(resolved)
    combo.setCurrentIndex(max(idx, 0))
    combo.blockSignals(blocker)
    return resolved


def source_reference_mode_from_combo(combo: QComboBox, index: int) -> str:
    """Resolve and normalize the selected source-reference mode."""
    return normalize_source_reference_mode(combo.itemData(index), default="EN")
