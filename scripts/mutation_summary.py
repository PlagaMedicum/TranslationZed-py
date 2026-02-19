#!/usr/bin/env python3
"""Summarize mutmut artifacts and apply optional mutation score gates."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

_COUNT_KEYS = ("killed", "survived", "timeout", "suspicious", "skipped")

_SUMMARY_PATTERNS = {
    "killed": re.compile(r"\bkilled\s*[:=]\s*(\d+)\b", flags=re.IGNORECASE),
    "survived": re.compile(r"\bsurvived\s*[:=]\s*(\d+)\b", flags=re.IGNORECASE),
    "timeout": re.compile(r"\btimeout(?:s)?\s*[:=]\s*(\d+)\b", flags=re.IGNORECASE),
    "suspicious": re.compile(
        r"\bsuspicious\s*[:=]\s*(\d+)\b", flags=re.IGNORECASE
    ),
    "skipped": re.compile(r"\bskipped\s*[:=]\s*(\d+)\b", flags=re.IGNORECASE),
}

_EMOJI_PATTERNS = {
    "killed": re.compile(r"🎉\s*(\d+)"),
    "survived": re.compile(r"🙁\s*(\d+)"),
    "timeout": re.compile(r"⏰\s*(\d+)"),
    "suspicious": re.compile(r"🤔\s*(\d+)"),
    "skipped": re.compile(r"🔇\s*(\d+)"),
}

_LINE_STATUS_PATTERNS = {
    "killed": re.compile(r"\bkilled\b", flags=re.IGNORECASE),
    "survived": re.compile(r"\bsurvived\b", flags=re.IGNORECASE),
    "timeout": re.compile(r"\btimeout(?:ed)?\b", flags=re.IGNORECASE),
    "suspicious": re.compile(r"\bsuspicious\b", flags=re.IGNORECASE),
    "skipped": re.compile(r"\bskipped\b", flags=re.IGNORECASE),
}


@dataclass(frozen=True, slots=True)
class MutationSummary:
    """Represent MutationSummary."""

    killed: int
    survived: int
    timeout: int
    suspicious: int
    skipped: int
    actionable_total: int
    total: int
    killed_percent: float


@dataclass(frozen=True, slots=True)
class MutationGateResult:
    """Represent MutationGateResult."""

    mode: str
    min_killed_percent: float
    passed: bool
    warned: bool
    message: str
    summary: MutationSummary


def _read_text(path: Path) -> str:
    """Read a UTF-8 text file as best effort."""
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _extract_summary_counts(text: str) -> dict[str, int]:
    """Extract status counts from summary-style output."""
    counts = dict.fromkeys(_COUNT_KEYS, 0)
    found = False
    for key, pattern in _SUMMARY_PATTERNS.items():
        matches = [int(value) for value in pattern.findall(text)]
        if matches:
            counts[key] = max(matches)
            found = True
    if found:
        return counts
    for key, pattern in _EMOJI_PATTERNS.items():
        matches = [int(value) for value in pattern.findall(text)]
        if matches:
            counts[key] = max(matches)
            found = True
    if found:
        return counts
    return {}


def _extract_line_counts(text: str) -> dict[str, int]:
    """Extract status counts from per-mutant line output."""
    counts = dict.fromkeys(_COUNT_KEYS, 0)
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        for key, pattern in _LINE_STATUS_PATTERNS.items():
            if pattern.search(line):
                counts[key] += 1
                break
    return counts


def summarize_mutation_outputs(run_log: str, results_text: str) -> MutationSummary:
    """Build mutation summary from mutmut run/results outputs."""
    merged = "\n".join(part for part in (run_log, results_text) if part.strip())
    counts = _extract_summary_counts(merged) or _extract_line_counts(results_text)
    killed = int(counts.get("killed", 0))
    survived = int(counts.get("survived", 0))
    timeout = int(counts.get("timeout", 0))
    suspicious = int(counts.get("suspicious", 0))
    skipped = int(counts.get("skipped", 0))
    actionable_total = killed + survived + timeout + suspicious
    total = actionable_total + skipped
    killed_percent = (100.0 * killed / actionable_total) if actionable_total else 0.0
    return MutationSummary(
        killed=killed,
        survived=survived,
        timeout=timeout,
        suspicious=suspicious,
        skipped=skipped,
        actionable_total=actionable_total,
        total=total,
        killed_percent=killed_percent,
    )


def evaluate_gate(
    summary: MutationSummary,
    *,
    mode: str,
    min_killed_percent: float,
) -> MutationGateResult:
    """Evaluate mutation score gate with warn/fail/off modes."""
    normalized_mode = mode.strip().lower()
    if normalized_mode not in {"warn", "fail", "off"}:
        raise ValueError("mode must be one of: warn, fail, off")

    if normalized_mode == "off":
        return MutationGateResult(
            mode=normalized_mode,
            min_killed_percent=min_killed_percent,
            passed=True,
            warned=False,
            message="mutation gate disabled (mode=off).",
            summary=summary,
        )

    if min_killed_percent <= 0:
        return MutationGateResult(
            mode=normalized_mode,
            min_killed_percent=min_killed_percent,
            passed=True,
            warned=False,
            message="mutation gate threshold disabled (min <= 0).",
            summary=summary,
        )

    if summary.actionable_total == 0:
        return MutationGateResult(
            mode=normalized_mode,
            min_killed_percent=min_killed_percent,
            passed=True,
            warned=False,
            message="mutation gate skipped: no actionable mutants found.",
            summary=summary,
        )

    if summary.killed_percent + 1e-9 >= min_killed_percent:
        return MutationGateResult(
            mode=normalized_mode,
            min_killed_percent=min_killed_percent,
            passed=True,
            warned=False,
            message=(
                "mutation gate passed: "
                f"killed {summary.killed_percent:.2f}% >= {min_killed_percent:.2f}%."
            ),
            summary=summary,
        )

    message = (
        "mutation gate below threshold: "
        f"killed {summary.killed_percent:.2f}% < {min_killed_percent:.2f}%."
    )
    return MutationGateResult(
        mode=normalized_mode,
        min_killed_percent=min_killed_percent,
        passed=normalized_mode != "fail",
        warned=normalized_mode == "warn",
        message=message,
        summary=summary,
    )


def _build_argument_parser() -> argparse.ArgumentParser:
    """Build CLI parser."""
    parser = argparse.ArgumentParser(
        description="Summarize mutmut artifacts and evaluate optional gate."
    )
    parser.add_argument("--run-log", type=Path, required=True)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--out-json", type=Path, required=True)
    parser.add_argument(
        "--mode",
        default="warn",
        choices=("warn", "fail", "off"),
        help="Gate mode (default: warn).",
    )
    parser.add_argument(
        "--min-killed-percent",
        type=float,
        default=0.0,
        help="Minimum killed percentage threshold (default: disabled).",
    )
    return parser


def main() -> int:
    """Run summary and optional gate evaluation."""
    parser = _build_argument_parser()
    args = parser.parse_args()

    run_log = _read_text(args.run_log)
    results_text = _read_text(args.results)
    summary = summarize_mutation_outputs(run_log, results_text)
    gate = evaluate_gate(
        summary,
        mode=args.mode,
        min_killed_percent=float(args.min_killed_percent),
    )

    payload = asdict(gate)
    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(
        json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(
        "mutation summary: "
        f"killed={summary.killed} survived={summary.survived} "
        f"timeout={summary.timeout} suspicious={summary.suspicious} "
        f"skipped={summary.skipped} actionable={summary.actionable_total} "
        f"killed_pct={summary.killed_percent:.2f}"
    )
    print(gate.message)
    return 0 if gate.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
