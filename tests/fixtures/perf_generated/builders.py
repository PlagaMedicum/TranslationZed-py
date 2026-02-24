"""Deterministic synthetic builders for 2k/20k perf-contract tests."""

from __future__ import annotations

from pathlib import Path


def build_translation_file(
    path: Path,
    *,
    entries: int,
    include_status_comments: bool = True,
) -> None:
    """Write a deterministic translation-like fixture with `entries` rows."""
    total = max(1, int(entries))
    lines: list[str] = []
    for idx in range(total):
        key = f"KEY_{idx:05d}"
        if idx % 17 == 0:
            value = f"Multi {idx:05d} alpha" + " " + "beta"
            line = f'{key} = "{value}" .. " + tail {idx:05d}"'
        elif idx % 11 == 0:
            value = f'Quoted \\"inner\\" value {idx:05d}'
            line = f'{key} = "{value}"'
        else:
            value = f"Value token {idx:05d}"
            line = f'{key} = "{value}"'
        if include_status_comments:
            if idx % 13 == 0:
                line += " -- TRANSLATED"
            elif idx % 19 == 0:
                line += " -- PROOFREAD"
            elif idx % 23 == 0:
                line += " -- FOR REVIEW"
        lines.append(line)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_tm_rows(*, entries: int) -> list[tuple[str, str, str]]:
    """Return deterministic TM rows with one strong query anchor neighborhood."""
    total = max(3, int(entries))
    rows: list[tuple[str, str, str]] = [
        ("anchor", "Drop all", "Пакінуць усё"),
        ("neighbor_a", "Drop one", "Скінуць адно"),
        ("neighbor_b", "Drop-all", "Скінуць-усё"),
    ]
    for idx in range(len(rows), total):
        key = f"noise_{idx:05d}"
        source = f"Noise token {idx:05d}"
        target = f"Шум {idx:05d}"
        rows.append((key, source, target))
    return rows


def build_tm_query_pack() -> tuple[str, ...]:
    """Return deterministic query pack for bit-stability perf contracts."""
    return (
        "Drop all",
        "Drop one",
        "drop all",
        "Drop-all",
        "Noise token 00010",
    )
