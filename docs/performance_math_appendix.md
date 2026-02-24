# TranslationZed-Py — Performance Math Appendix
_Last updated: 2026-02-24_

## 1) Purpose

This appendix records concise mathematical models and proof obligations for
performance-sensitive algorithms. It is used to reduce accidental behavioral
regressions during optimization refactors.

Normative behavior still belongs to:
- `docs/translation_zed_py_technical_specification.md`
- `docs/translation_zed_py_use_case_ux_specification.md`
- `docs/testing_strategy.md`

## 2) Parser Cost Model

For one file parse:

`T_parse = T_tokenize + T_offset + T_finalize`

Where:
- `T_tokenize`: lexical scan and token classification
- `T_offset`: byte-offset map construction for char->byte spans
- `T_finalize`: entry assembly (segments/spans/status)

### 2.1 Amdahl Target

If desired global speed factor is `F = 0.55` (45% faster), and improved fraction
is `p`, required speedup of improved component is:

`S_required = p / (F - (1 - p))`

For example, when `p = 0.70`:

`S_required = 0.70 / (0.55 - 0.30) = 2.8`

So the optimized fraction must be about `2.8x` faster.

### 2.2 Equivalence Obligations

Optimized parser path must preserve:
1) key/value/status sequence,
2) byte span boundaries,
3) concat segment lengths and gap bytes,
4) deterministic handling of malformed-but-supported inputs.

## 3) TM Query Cost Model

For one query:

`T_tm = T_sql + N_c * (T_ratio + T_token + T_phrase + T_overlap)`

Where:
- `N_c`: fuzzy candidate count after SQL retrieval and dedupe
- `T_ratio`: sequence similarity cost
- `T_token`: tokenization/stemming cost
- `T_phrase`: composed-phrase matching cost
- `T_overlap`: token overlap scoring cost

Optimization levers without semantic drift:
1) reduce repeated token/stem recomputation,
2) reduce repeated per-candidate feature extraction,
3) keep deterministic bounded caches for reusable features.

## 4) Search Wave-2 Model

Legacy shape:

`T_search_old ~= N_rows * (C_lower + C_query_split + C_match)`

Optimized shape:

`T_search_new ~= N_rows * (C_lower + C_match) + C_query_split`

Interpretation: query decomposition/splitting is hoisted out of the row loop.

## 5) Bounded Cache Invariants

Any new hot-path cache must satisfy:
1) fixed hard cap `K`,
2) deterministic eviction order (LRU),
3) no unbounded growth across long sessions,
4) no behavioral drift from cache hits/misses.

Proposed cap family:
- token cache: 8192 entries
- stem cache: 4096 entries
- phrase cache: 2048 entries

## 6) Perf Contract Measurement

For parser/TM performance contracts:
1) use same-run A/B comparison (legacy vs optimized path),
2) test at dual scales: fixture-scale (`~2k`) and synthetic scale (`20k`),
3) compare medians, not single-shot timings,
4) enforce strict semantic equivalence before accepting speed gains.

## 7) Dependency Adoption Proof Gate

A performance dependency is admissible only if all pass:
1) license compatibility,
2) mature maintained upstream,
3) Python 3.10+ cross-platform support,
4) no hidden side effects,
5) measured `>15%` gain vs optimized in-project baseline,
6) bit-stable output equivalence for locked contracts.

If any fails: dependency is rejected and rationale is documented.
