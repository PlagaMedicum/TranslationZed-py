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
        root = tmp_path / case_label
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
