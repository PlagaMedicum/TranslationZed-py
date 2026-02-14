from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from translationzed_py.core.tm_store import TMStore


def _load_corpus() -> dict[str, Any]:
    path = Path("tests/fixtures/tm_ranking/corpus.json")
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    assert payload.get("version") == 1
    return payload


def _insert_entry(
    store: TMStore,
    root: Path,
    source_locale: str,
    target_locale: str,
    entry: dict[str, Any],
) -> None:
    origin = str(entry.get("origin", "project")).strip().lower()
    source_text = str(entry["source"])
    target_text = str(entry["target"])
    updated_at = int(entry.get("updated_at", 1))
    if origin == "import":
        tm_name = str(entry.get("tm_name", "fixture_tm")).strip() or "fixture_tm"
        tm_path = str(entry.get("tm_path", root / ".tzp" / "tms" / f"{tm_name}.tmx"))
        store.insert_import_pairs(
            [(source_text, target_text)],
            source_locale=source_locale,
            target_locale=target_locale,
            tm_name=tm_name,
            tm_path=tm_path,
            updated_at=updated_at,
        )
        return
    key = str(entry.get("key", f"key_{updated_at}"))
    file_path = str(root / target_locale / "ui.txt")
    store.upsert_project_entries(
        [(key, source_text, target_text)],
        source_locale=source_locale,
        target_locale=target_locale,
        file_path=file_path,
        updated_at=updated_at,
    )


def _first_index_by_source(matches) -> dict[str, int]:
    out: dict[str, int] = {}
    for idx, match in enumerate(matches):
        out.setdefault(match.source_text, idx)
    return out


def _diagnostics_snapshot(matches) -> dict[str, float]:
    visible = len(matches)
    fuzzy = sum(1 for match in matches if match.score < 100)
    unique_sources = len({match.source_text for match in matches})
    recall_density = float(unique_sources) / float(visible) if visible else 0.0
    return {
        "visible": float(visible),
        "fuzzy": float(fuzzy),
        "unique_sources": float(unique_sources),
        "recall_density": recall_density,
    }


def _safe_case_label(label: str) -> str:
    return "".join(ch if ch.isalnum() or ch in {"_", "-", "."} else "_" for ch in label)


def test_tm_ranking_corpus(tmp_path: Path) -> None:
    corpus = _load_corpus()
    cases = corpus.get("cases", [])
    assert isinstance(cases, list) and cases
    profiles = {str(case.get("profile", "synthetic_core")) for case in cases}
    assert len(profiles) >= 2

    for case in cases:
        profile = str(case.get("profile", "synthetic_core"))
        case_id = str(case.get("id", "unknown"))
        case_label = f"{profile}:{case_id}"
        root = tmp_path / _safe_case_label(case_label)
        root.mkdir(parents=True, exist_ok=True)
        store = TMStore(root)
        try:
            source_locale = str(case["source_locale"]).upper()
            target_locale = str(case["target_locale"]).upper()
            for entry in case["entries"]:
                _insert_entry(
                    store,
                    root,
                    source_locale=source_locale,
                    target_locale=target_locale,
                    entry=entry,
                )
            matches = store.query(
                str(case["query"]),
                source_locale=source_locale,
                target_locale=target_locale,
                limit=int(case.get("limit", 12)),
                min_score=int(case.get("min_score", 5)),
                origins=case.get("origins"),
            )
            sources = [match.source_text for match in matches]
            indices = _first_index_by_source(matches)
            unique_sources = set(sources)

            expect_min_results = case.get("expect_min_results")
            if expect_min_results is not None:
                assert len(matches) >= int(expect_min_results), (
                    f"{case_label}: expected at least {expect_min_results} results, "
                    f"got {len(matches)}"
                )

            expect_min_unique_sources = case.get("expect_min_unique_sources")
            if expect_min_unique_sources is not None:
                assert len(unique_sources) >= int(expect_min_unique_sources), (
                    f"{case_label}: expected at least {expect_min_unique_sources} unique "
                    f"sources, got {len(unique_sources)}"
                )

            expect_diagnostics = case.get("expect_diagnostics")
            if isinstance(expect_diagnostics, dict):
                snap = _diagnostics_snapshot(matches)
                for metric, expected in expect_diagnostics.items():
                    metric_name = str(metric)
                    if metric_name.endswith("_min"):
                        name = metric_name[: -len("_min")]
                        op = "min"
                    elif metric_name.endswith("_max"):
                        name = metric_name[: -len("_max")]
                        op = "max"
                    else:
                        name = metric_name
                        op = "eq"
                    actual = snap.get(name)
                    assert (
                        actual is not None
                    ), f"{case_label}: unknown diagnostics metric '{metric}'"
                    expected_f = float(expected)
                    if op == "min":
                        assert actual >= expected_f, (
                            f"{case_label}: diagnostics {name}={actual:.2f} "
                            f"< min {expected_f:.2f}"
                        )
                    elif op == "max":
                        assert actual <= expected_f, (
                            f"{case_label}: diagnostics {name}={actual:.2f} "
                            f"> max {expected_f:.2f}"
                        )
                    else:
                        assert abs(actual - expected_f) <= 1e-6, (
                            f"{case_label}: diagnostics {name}={actual:.2f} "
                            f"!= expected {expected_f:.2f}"
                        )

            expect_top = case.get("expect_top")
            if expect_top:
                assert matches, f"{case_label}: expected top match {expect_top}"
                assert matches[0].source_text == expect_top, (
                    f"{case_label}: top was {matches[0].source_text}, "
                    f"expected {expect_top}"
                )

            for expected in case.get("expect_present", []):
                if isinstance(expected, str):
                    src = expected
                    min_score = None
                else:
                    src = str(expected["source"])
                    min_score = expected.get("min_score")
                assert src in indices, f"{case_label}: missing expected source '{src}'"
                if min_score is not None:
                    match = next(item for item in matches if item.source_text == src)
                    assert match.score >= int(min_score), (
                        f"{case_label}: score {match.score} "
                        f"< {min_score} for '{src}'"
                    )

            for src in case.get("expect_absent", []):
                assert (
                    str(src) not in sources
                ), f"{case_label}: unexpected source '{src}'"

            for before_src, after_src in case.get("expect_order", []):
                assert (
                    before_src in indices
                ), f"{case_label}: missing ordering source '{before_src}'"
                assert (
                    after_src in indices
                ), f"{case_label}: missing ordering source '{after_src}'"
                assert (
                    indices[before_src] < indices[after_src]
                ), f"{case_label}: expected '{before_src}' before '{after_src}'"
        finally:
            store.close()
