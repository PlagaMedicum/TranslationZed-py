# TranslationZed-Py TM Ranking Algorithm
_Last updated: 2026-03-01_

## 1) Purpose

This document defines the Translation Memory (TM) retrieval and ranking algorithm
used by `core.tm_store`. It is normative for TM suggestion relevance behavior in
the TM panel.

Goals:
- Keep exact matches first.
- Keep useful fuzzy neighbors visible even when prefixes differ.
- Support prefix/affix token variants (for example, `favorite` -> `favorites`,
  `run` -> `running`).
- Avoid substring-only noise for short one-token queries.

## 1.1) Implementation Module Map (A15-TM-RF1)

Current implementation ownership:
1. `translationzed_py/core/tm_store.py`
   1. database lifecycle, query cache, and top-level `TMStore.query(...)` orchestration.
2. `translationzed_py/core/tm_query_engine.py`
   1. exact+fuzzy query composition and candidate retrieval flow.
3. `translationzed_py/core/tm_query_policy.py`
   1. normalization policy, adaptive length-band policy, and oversized-candidate guard.
4. `translationzed_py/core/tm_query_scoring.py`
   1. scoring gates, score construction, and deterministic tie-break ordering.
5. `translationzed_py/core/tm_query_contracts.py`
   1. internal dataclass contracts for runtime policy/config/metrics.
6. `translationzed_py/core/tm_query_text.py`
   1. token and composed-phrase text-matching primitives.
7. `translationzed_py/core/tm_store_support.py`
   1. locale/origin/status normalization and sqlite conflict helper predicates.

## 2) Query Inputs

- `source_text`: current EN source text from selected row.
- `source_locale`, `target_locale`: locale pair.
- `min_score`: integer threshold `5..100` (default UI value `50`).
- `origins`: `project`, `import`, or both.
- `limit`: max suggestions returned to UI; scaled by `min_score` for high-recall mode:
  - `<=10`: 200
  - `<=20`: 120
  - `<=40`: 60
  - `>40`: 30

## 3) Normalization And Tokens

### 3.1 Normalization

- Query and stored source strings are normalized with:
  - lowercase conversion,
  - whitespace collapsing (`" ".join(text.lower().split())`).

### 3.4 Partial Formatting-Wrapper Cleanup (Long-Variant Contract)

For TM fuzzy matching only, normalization is allowed to strip presentation wrappers
that do not carry semantic content:
- markdown emphasis wrappers (`**...**`, `__...__`, `*...*`, `_..._`),
- markdown strike wrappers (`~~...~~`),
- markdown/code wrappers (`` `...` ``),
- list-prefix markers (`- `, `* `, `1) `) at line starts.

Normalization MUST keep semantic content tokens intact:
- words and punctuation that affect meaning,
- `@mentions`,
- timestamps/dates,
- placeholders/tags (for example `<LINE>` / `<BR>`).

### 3.2 Tokenization

- Tokens are extracted with `re.findall(r"\\w+", text, flags=re.UNICODE)`.
- Tokens shorter than 2 chars are ignored.
- Repeated query/candidate tokenization is cached with deterministic bounded LRU:
  token cache cap `8192`.

### 3.3 Token Match Semantics (prefix/affix-aware)

Token matching uses two layers:
- generic (all source locales): exact, one-char typo tolerance, prefix/suffix/substring guards;
- EN-adapted (only when `source_locale == EN`): lightweight affix stemming.

Two tokens are considered matching when one of the rules holds:
- exact equality;
- common lightweight EN stem equality (`ies`, `ing`, `ed`, `ers`, `er`, `es`, `s`, `ly`,
  with doubled-consonant normalization like `running` -> `run`), EN-mode only;
- one-character substitution tolerance for token length >= 4 (for typo-neighbors like
  `drop` vs `drap`);
- prefix/suffix relation for token length >= 4 with ratio guard
  (`len(shorter) / len(longer) >= 0.50`);
- contained-substring relation for token length >= 4 with stricter ratio guard
  (`>= 0.67`).

This enables CAT-like prefix/affix matching on EN source strings without introducing
heavy NLP dependencies.
- Stemming and token-match helper paths are cached with deterministic bounded LRU:
  stem cache cap `4096`, token-match cache cap `8192`.

## 4) Retrieval Pipeline

### 4.1 Exact Stage

- Query `tm_entries` by `source_norm` equality.
- Exact matches are score `100`.
- Reserve fuzzy capacity:
  - regular query: reserve `_FUZZY_RESERVED_SLOTS` (3),
  - short query (`len(norm) <= 4`): reserve `_SHORT_QUERY_RESERVED_SLOTS` (6).

### 4.2 Fuzzy Candidate Pools

Fuzzy candidates are built as a **union** of bounded pools (de-duplicated):

- `prefix pool`: `source_prefix = _prefix(query_norm)` + length band.
- `token pool`: rows containing longest query token (`instr(source_norm, token) > 0`)
  + length band, ordered to prefer token boundaries/whole-token positions.
- `fallback pool`: locale pair + length band only.

Length band:
- default: `source_len` in `[0.6 * query_len, 1.4 * query_len]` (or `+10` for short text),
- short query (`<=4`): widened to `[1, max(previous, 40)]`.

Pool order:
- short query: token -> prefix -> fallback,
- regular query: prefix -> token -> fallback.

All pools are bounded and merged with de-duplication to keep query latency stable.

### 4.3 TM Long-Variant Detection Contract

This section is normative for screenshot-style edited long sentences where the
candidate text is significantly longer than the query because of inserted
phrases/formatting noise.

Define:
- `q = normalize(query)`
- `c = normalize(candidate)`
- `Lq = |q|`
- `Lc = |c|`
- `k = token_count(q)`

Base candidate-length band:

$$
L_{\text{min\_base}} = \max(1,\lfloor 0.6 \cdot L_q \rfloor)
$$

$$
L_{\text{max\_base}} =
\begin{cases}
\lfloor 1.4 \cdot L_q \rfloor, & L_q > 5 \\
L_q + 10, & \text{otherwise}
\end{cases}
$$

Adaptive long multi-token trigger:

$$
\text{is\_long\_multi} := (k \ge 8) \land (L_q \ge 80)
$$

If `is_long_multi`:

$$
L_{\text{min}} = \max(1,\lfloor 0.5 \cdot L_q \rfloor)
$$

$$
L_{\text{max}} = \max\left(L_{\text{max\_base}}, \lfloor 1.85 \cdot L_q \rfloor\right)
$$

Else:

$$
L_{\text{min}} = L_{\text{min\_base}}, \quad L_{\text{max}} = L_{\text{max\_base}}
$$

Oversized precision guard (only for candidates where `Lc > Lmax_base`):

$$
\text{keep}(c) \iff
\left(\text{overlap} \ge 0.55\right)
\lor
\left(\text{composed\_phrase} = \text{true} \land \text{ratio} \ge 0.70\right)
$$

Invariants:
- exact matches remain score `100`,
- fuzzy non-exact matches stay capped below exact (`<=99`),
- tie-break ordering semantics remain unchanged.

## 5) Relevance Gates

Before scoring, candidate rows pass gates:

- If query has one token:
  - require token overlap >= 0.5 **or** composed-phrase match.
  - This blocks substring-only noise (for example, `all` should not match `small`).
- If query has 2+ tokens:
  - accept candidate when any is true:
    - overlap >= 0.34,
    - `SequenceMatcher` ratio >= 0.75,
    - composed-phrase match.

Composed-phrase match:
- one-token query: token-aware matching against candidate tokens,
- multi-token query: ordered token composition match.
- Phrase-match helper is cached with deterministic bounded LRU:
  phrase cache cap `2048`.

## 6) Scoring

For each accepted fuzzy candidate:

- `base_score = round(100 * sequence_ratio)`
- `token_bonus = round(6 * soft_token_overlap + 4 * exact_token_overlap)`
- `score = min(100, base_score + token_bonus)`
- composed-phrase floor:
  - `>= 90` for multi-token composed phrase,
  - `>= 85` for one-token composed phrase.
- non-exact fuzzy cap:
  - fuzzy candidates are capped to `99` even if bonus would push to `100`.

Diagnostics:
- UI displays `score` (ranked) and `raw_score` (base character similarity) for
  diagnostics.

Notes:
- Exact matches stay fixed at `100`.
- `min_score` is applied after scoring.
- Origin filters (`project` only / `import` only / both) use identical fuzzy candidate
  retrieval logic; fuzzy recall must not collapse when one origin is disabled.

## 7) Ordering (Tie-Break)

Suggestions are sorted by:
1. for multi-token queries, token-count delta to query ascending,
2. score descending,
3. absolute source-length delta ascending (closer lengths first),
4. origin preference (`project` before `import`),
5. `updated_at` descending.

## 8) Behavioral Guarantees

The algorithm must satisfy:
- `Drop one` can surface `Drop-all`/`Drop all` at low thresholds (for example 25%).
- `Drop all` can surface `Drop one` at low thresholds (for example 5%).
- `All` can surface `Apply all` at low thresholds.
- `Official: Rest` can surface `Official: Run` and vice versa at low thresholds.
- `Make item` can surface phrase-expansion neighbors such as `Make new item`.
- `All` should not surface substring-only noise like `Small crate`.
- Prefix/affix neighbors (`Run`, `Running`, `Runner`) remain query-visible.
- In low-threshold mode (`min_score <= 10`), short action phrases must return
  multiple fuzzy neighbors (not only exact + one fallback) in dense candidate pools.

## 9) Test Contract

Regression tests cover:
- short-query neighbor retrieval under dense candidate sets,
- multi-token non-prefix neighbor retrieval,
- substring-noise suppression for one-token queries,
- affix/prefix token matching visibility.
- deterministic corpus acceptance scenarios loaded from
  `tests/fixtures/tm_ranking/corpus.json` and executed by
  `tests/test_tm_ranking_corpus.py`.
  The corpus is split into multiple profiles and CI enforces at least two:
  - `synthetic_core`: targeted algorithm edge-cases and tie-break contracts.
  - `pz_fixture_like`: PZ-style tagged/phrase patterns and dense phrase pools.
- Corpus assertions also enforce minimum-recall density for key low-threshold
  scenarios (`expect_min_results`, `expect_min_unique_sources`) so regressions
  that collapse to exact-only behavior fail CI.
- Production-like corpus slices also assert diagnostics snapshot minima
  (`visible`, `fuzzy`, `unique_sources`, `recall_density`) to keep recall
  quality observable in CI.
- Bit-stability and performance contracts (A12):
  - `tests/test_tm_query_perf_contract.py` compares optimized path vs legacy helper
    path and asserts identical ordered results/scores for fixed query pack,
  - same module enforces 20k-scale median speedup contract (default `>=35%`),
  - `tests/test_tm_store_cache_caps.py` enforces bounded cache sizes and
    deterministic LRU-eviction behavior.

See `tests/test_tm_store.py` and `tests/test_tm_ranking_corpus.py` for executable examples.

## 10) Scope Limits (Current)

Out of scope for the current implementation:
- context-ID and neighboring-segment weighting;
- inline-tag/placeholder penalty model;
- language-specific lemmatizers beyond lightweight EN-affix normalization;
- cross-locale source matching.
