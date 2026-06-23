# On-Demand Contract Context

The source tree and focused API pages are authoritative. A generated index is useful when an agent
needs compact symbol context for a small set of modules, but a tracked full-core JSON file created
frequent unrelated diffs and duplicated source docstrings.

Generate targeted JSON to stdout:

```bash
python scripts/generate_contract_index.py \
  --module translationzed_py.core.parser \
  --module translationzed_py.core.saver
```

Generate public symbols only:

```bash
python scripts/generate_contract_index.py \
  --module translationzed_py.core.file_workflow \
  --public-only
```

Write a disposable artifact:

```bash
python scripts/generate_contract_index.py \
  --module translationzed_py.core.tm_query_engine \
  --out artifacts/context/tm-query.json
```

Use `docs/reference/module_map.md` to choose modules before generating broader context. Generated
artifacts are ignored work products and must not be treated as behavior specifications.
