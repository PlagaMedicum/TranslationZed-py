#!/usr/bin/env python3
"""Produce statistically robust parser/TM/search performance analysis reports."""

from __future__ import annotations

import argparse
import cProfile
import io
import json
import pstats
import random
import statistics
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from translationzed_py.core import SearchField, SearchRow, parse, parse_lazy, search
from translationzed_py.core.tm_store import TMStore


@dataclass(frozen=True, slots=True)
class DistributionStats:
    """Summary stats for a repeated timing distribution."""

    median_ms: float
    mad_ms: float
    p90_ms: float
    ci95_low_ms: float
    ci95_high_ms: float


@dataclass(frozen=True, slots=True)
class PerfSample:
    """One measured workload sample with robust statistics."""

    name: str
    scale: str
    repeats: int
    stats: DistributionStats


@dataclass(frozen=True, slots=True)
class ProfileDump:
    """One cProfile dump summary with hotspot share details."""

    name: str
    scale: str
    top: list[str]
    total_time_s: float
    offset_time_s: float
    search_focus_time_s: dict[str, float]


def _build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Analyze parser/TM/search performance on fixture-scale and synthetic 20k scale."
        )
    )
    parser.add_argument("--out-json", type=Path)
    parser.add_argument(
        "--fixture-root",
        type=Path,
        default=Path("tests/fixtures/perf_root/BE"),
        help="Fixture root containing SurvivalGuide_BE.txt / Recorded_Media_BE.txt.",
    )
    parser.add_argument(
        "--synthetic-entries",
        type=int,
        default=20_000,
        help="Synthetic entry count used for stress-scale analysis.",
    )
    parser.add_argument("--repeats", type=int, default=9)
    parser.add_argument("--profile-top", type=int, default=12)
    parser.add_argument(
        "--bootstrap-iterations",
        type=int,
        default=300,
        help="Bootstrap iterations for timing CI estimation.",
    )
    parser.add_argument("--seed", type=int, default=42)
    return parser


def _bootstrap_ci(
    values: list[float], *, seed: int, iterations: int
) -> tuple[float, float]:
    if not values:
        return (0.0, 0.0)
    if len(values) == 1:
        return (values[0], values[0])
    rng = random.Random(seed)
    n = len(values)
    medians: list[float] = []
    for _ in range(max(10, iterations)):
        draw = [values[rng.randrange(n)] for _ in range(n)]
        medians.append(float(statistics.median(draw)))
    medians.sort()
    low_idx = int(round(0.025 * (len(medians) - 1)))
    high_idx = int(round(0.975 * (len(medians) - 1)))
    return medians[low_idx], medians[high_idx]


def _distribution_stats(
    values: list[float],
    *,
    seed: int,
    iterations: int,
) -> DistributionStats:
    median_ms = float(statistics.median(values))
    mad_ms = float(statistics.median(abs(sample - median_ms) for sample in values))
    sorted_values = sorted(values)
    p90_index = int(round(0.9 * (len(sorted_values) - 1)))
    p90_ms = float(sorted_values[p90_index])
    ci_low_ms, ci_high_ms = _bootstrap_ci(
        values,
        seed=seed,
        iterations=iterations,
    )
    return DistributionStats(
        median_ms=median_ms,
        mad_ms=mad_ms,
        p90_ms=p90_ms,
        ci95_low_ms=ci_low_ms,
        ci95_high_ms=ci_high_ms,
    )


def _measure_distribution(
    repeats: int,
    fn: Callable[[], object],
    *,
    seed: int,
    iterations: int,
) -> tuple[list[float], DistributionStats]:
    values: list[float] = []
    for _ in range(max(1, repeats)):
        start = time.perf_counter()
        fn()
        values.append((time.perf_counter() - start) * 1000.0)
    return values, _distribution_stats(values, seed=seed, iterations=iterations)


def _profile_summary(
    fn: Callable[[], object], top_n: int
) -> tuple[list[str], float, float, dict[str, float]]:
    pr = cProfile.Profile()
    pr.enable()
    fn()
    pr.disable()
    stream = io.StringIO()
    stats = pstats.Stats(pr, stream=stream).strip_dirs().sort_stats("cumtime")
    stats.print_stats(max(1, top_n))
    lines = [line.rstrip() for line in stream.getvalue().splitlines() if line.strip()]

    total_time_s = float(stats.total_tt)
    offset_time_s = 0.0
    search_focus_time_s: dict[str, float] = {
        "iter_matches": 0.0,
        "match_literal": 0.0,
        "find_literal_span": 0.0,
    }
    for (_filename, _lineno, func_name), sample in stats.stats.items():
        if func_name.startswith("_build_offset_map"):
            _cc, _nc, _tt, ct, _callers = sample
            offset_time_s += float(ct)
        if func_name in {"iter_matches", "_iter_matches_with_plan"}:
            _cc, _nc, _tt, ct, _callers = sample
            search_focus_time_s["iter_matches"] += float(ct)
        if func_name in {"_matches_literal", "_match_literal_index"}:
            _cc, _nc, _tt, ct, _callers = sample
            search_focus_time_s["match_literal"] += float(ct)
        if func_name == "_find_literal_span":
            _cc, _nc, _tt, ct, _callers = sample
            search_focus_time_s["find_literal_span"] += float(ct)
    return lines[-max(1, top_n) :], total_time_s, offset_time_s, search_focus_time_s


def _required_component_speedup(p: float, target_factor: float = 0.55) -> float:
    denominator = target_factor - (1.0 - p)
    if denominator <= 0.0:
        return float("inf")
    return p / denominator


def _write_synthetic_file(path: Path, entries: int) -> None:
    lines = [f'K_{idx:05d} = "Value {idx:05d}"' for idx in range(max(1, entries))]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _build_tm_rows(entries: int) -> list[tuple[str, str, str]]:
    rows = [
        ("anchor", "Drop all", "Пакінуць усё"),
        ("neighbor_a", "Drop one", "Скінуць адно"),
        ("neighbor_b", "Drop-all", "Скінуць-усё"),
    ]
    rows.extend(
        (
            f"k_{idx:05d}",
            f"Noise token {idx:05d}",
            f"Noise tr {idx:05d}",
        )
        for idx in range(len(rows), max(1, entries))
    )
    return rows


def _format_table(samples: list[PerfSample]) -> str:
    header = "Workload                         Scale     Median  MAD   P90   CI95-low CI95-high"
    sep = "-" * len(header)
    lines = [header, sep]
    for sample in samples:
        lines.append(
            " ".join(
                [
                    f"{sample.name:<32}",
                    f"{sample.scale:<9}",
                    f"{sample.stats.median_ms:>7.2f}",
                    f"{sample.stats.mad_ms:>5.2f}",
                    f"{sample.stats.p90_ms:>5.2f}",
                    f"{sample.stats.ci95_low_ms:>8.2f}",
                    f"{sample.stats.ci95_high_ms:>9.2f}",
                ]
            )
        )
    return "\n".join(lines)


def main() -> int:
    """Run analysis workloads and print/write aggregate performance report."""
    args = _build_argument_parser().parse_args()
    fixture_root = args.fixture_root.resolve()
    sg = fixture_root / "SurvivalGuide_BE.txt"
    rm = fixture_root / "Recorded_Media_BE.txt"
    if not sg.exists() or not rm.exists():
        raise SystemExit(
            "Missing perf fixtures under "
            f"{fixture_root}; expected SurvivalGuide_BE.txt and "
            "Recorded_Media_BE.txt."
        )

    repeats = max(1, int(args.repeats))
    top_n = max(1, int(args.profile_top))
    synthetic_entries = max(100, int(args.synthetic_entries))
    bootstrap_iterations = max(50, int(args.bootstrap_iterations))

    samples: list[PerfSample] = []
    profiles: list[ProfileDump] = []
    parser_amdahl: list[dict[str, float | str]] = []

    fixture_rows: list[SearchRow] | None = None

    def _fixture_parse_lazy() -> int:
        parsed = parse_lazy(sg, encoding="utf-8")
        return len(parsed.entries)

    def _fixture_parse_eager() -> int:
        parsed = parse(rm, encoding="utf-8")
        return len(parsed.entries)

    def _fixture_search() -> int:
        nonlocal fixture_rows
        if fixture_rows is None:
            parsed = parse(rm, encoding="utf-8")
            fixture_rows = [
                SearchRow(rm, idx, entry.key, "", entry.value)
                for idx, entry in enumerate(parsed.entries)
            ]
        return len(search(fixture_rows, "item", SearchField.TRANSLATION, False))

    with tempfile.TemporaryDirectory(prefix="tzp-perf-analyze-") as temp_root:
        temp = Path(temp_root)
        synthetic_file = temp / "synthetic_20k.txt"
        _write_synthetic_file(synthetic_file, synthetic_entries)
        synthetic_rows: list[SearchRow] | None = None
        store = TMStore(temp)
        try:
            tm_rows = _build_tm_rows(synthetic_entries)
            store.upsert_project_entries(
                tm_rows,
                source_locale="EN",
                target_locale="BE",
                file_path="synthetic.txt",
                updated_at=1,
            )

            def _synthetic_parse_lazy() -> int:
                parsed = parse_lazy(synthetic_file, encoding="utf-8")
                return len(parsed.entries)

            def _synthetic_parse_eager() -> int:
                parsed = parse(synthetic_file, encoding="utf-8")
                return len(parsed.entries)

            def _synthetic_search() -> int:
                nonlocal synthetic_rows
                if synthetic_rows is None:
                    parsed = parse(synthetic_file, encoding="utf-8")
                    synthetic_rows = [
                        SearchRow(synthetic_file, idx, entry.key, "", entry.value)
                        for idx, entry in enumerate(parsed.entries)
                    ]
                return len(
                    search(synthetic_rows, "value", SearchField.TRANSLATION, False)
                )

            def _tm_query() -> int:
                matches = store.query(
                    "Drop all",
                    source_locale="EN",
                    target_locale="BE",
                    limit=20,
                    min_score=5,
                )
                return len(matches)

            workload_map: list[tuple[str, str, Callable[[], object]]] = [
                ("parse_lazy", "fixture", _fixture_parse_lazy),
                ("parse_eager", "fixture", _fixture_parse_eager),
                ("search_translation", "fixture", _fixture_search),
                ("parse_lazy", "synthetic20k", _synthetic_parse_lazy),
                ("parse_eager", "synthetic20k", _synthetic_parse_eager),
                ("search_translation", "synthetic20k", _synthetic_search),
                ("tm_query", "synthetic20k", _tm_query),
            ]

            for idx, (name, scale, fn) in enumerate(workload_map):
                _, stats = _measure_distribution(
                    repeats,
                    fn,
                    seed=args.seed + idx,
                    iterations=bootstrap_iterations,
                )
                samples.append(
                    PerfSample(name=name, scale=scale, repeats=repeats, stats=stats)
                )
                top, total_time_s, offset_time_s, search_focus_time_s = (
                    _profile_summary(fn, top_n)
                )
                profiles.append(
                    ProfileDump(
                        name=name,
                        scale=scale,
                        top=top,
                        total_time_s=total_time_s,
                        offset_time_s=offset_time_s,
                        search_focus_time_s=search_focus_time_s,
                    )
                )
                if name.startswith("parse") and total_time_s > 0.0:
                    p = max(0.0, min(1.0, offset_time_s / total_time_s))
                    parser_amdahl.append(
                        {
                            "name": name,
                            "scale": scale,
                            "offset_share": p,
                            "required_component_speedup_for_45pct_total": (
                                _required_component_speedup(p)
                            ),
                        }
                    )
        finally:
            store.close()

    print(_format_table(samples))
    if parser_amdahl:
        print("\nParser Amdahl guidance (target total factor = 0.55):")
        for item in parser_amdahl:
            print(
                "  - "
                f"{item['name']} [{item['scale']}]: "
                f"offset-share={float(item['offset_share']):.4f}, "
                "required-offset-speedup="
                f"{float(item['required_component_speedup_for_45pct_total']):.4f}"
            )
    search_profiles = [
        dump
        for dump in profiles
        if dump.name == "search_translation" and dump.scale == "synthetic20k"
    ]
    if search_profiles:
        print("\nSearch synthetic20k hotspot shares:")
        for dump in search_profiles:
            if dump.total_time_s <= 0.0:
                continue
            iter_share = (
                dump.search_focus_time_s["iter_matches"] / dump.total_time_s
            ) * 100.0
            literal_share = (
                dump.search_focus_time_s["match_literal"] / dump.total_time_s
            ) * 100.0
            print(
                "  - "
                f"iter_matches={iter_share:.2f}% "
                f"literal_match={literal_share:.2f}%"
            )

    payload = {
        "samples": [
            {
                "name": sample.name,
                "scale": sample.scale,
                "repeats": sample.repeats,
                "stats": {
                    "median_ms": sample.stats.median_ms,
                    "mad_ms": sample.stats.mad_ms,
                    "p90_ms": sample.stats.p90_ms,
                    "ci95_low_ms": sample.stats.ci95_low_ms,
                    "ci95_high_ms": sample.stats.ci95_high_ms,
                },
            }
            for sample in samples
        ],
        "profiles": [
            {
                "name": dump.name,
                "scale": dump.scale,
                "top": dump.top,
                "total_time_s": dump.total_time_s,
                "offset_time_s": dump.offset_time_s,
                "search_focus_time_s": dump.search_focus_time_s,
            }
            for dump in profiles
        ],
        "parser_amdahl": parser_amdahl,
    }
    if args.out_json:
        args.out_json.parent.mkdir(parents=True, exist_ok=True)
        args.out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"wrote analysis JSON: {args.out_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
