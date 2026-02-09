# TranslationZed-Py TM Ranking Algorithm
_Last updated: 2026-02-09_

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

## 2) Query Inputs

- `source_text`: current EN source text from selected row.
- `source_locale`, `target_locale`: locale pair.
- `min_score`: integer threshold `5..100` (default UI value `50`).
- `origins`: `project`, `import`, or both.
- `limit`: max suggestions returned to UI.

## 3) Normalization And Tokens

### 3.1 Normalization

- Query and stored source strings are normalized with:
  - lowercase conversion,
  - whitespace collapsing (`" ".join(text.lower().split())`).

### 3.2 Tokenization

- Tokens are extracted with `re.findall(r"\\w+", text, flags=re.UNICODE)`.
- Tokens shorter than 2 chars are ignored.

### 3.3 Token Match Semantics (prefix/affix-aware)

Two tokens are considered matching when one of the rules holds:
- exact equality;
- common lightweight stem equality (`ies`, `ing`, `ed`, `ers`, `er`, `es`, `s`, `ly`,
  with doubled-consonant normalization like `running` -> `run`);
- prefix/suffix relation for token length >= 4 with ratio guard
  (`len(shorter) / len(longer) >= 0.50`);
- contained-substring relation for token length >= 4 with stricter ratio guard
  (`>= 0.67`).

This is the mechanism that enables prefix/affix matching without rewriting TM data.

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

Notes:
- Exact matches stay fixed at `100`.
- `min_score` is applied after scoring.

## 7) Ordering (Tie-Break)

Suggestions are sorted by:
1. score descending,
2. absolute source-length delta ascending (closer lengths first),
3. origin preference (`project` before `import`),
4. `updated_at` descending.

## 8) Behavioral Guarantees

The algorithm must satisfy:
- `Drop one` can surface `Drop-all`/`Drop all` at low thresholds (for example 25%).
- `All` can surface `Apply all` at low thresholds.
- `All` should not surface substring-only noise like `Small crate`.
- Prefix/affix neighbors (`Run`, `Running`, `Runner`) remain query-visible.

## 9) Test Contract

Regression tests cover:
- short-query neighbor retrieval under dense candidate sets,
- multi-token non-prefix neighbor retrieval,
- substring-noise suppression for one-token queries,
- affix/prefix token matching visibility.

See `tests/test_tm_store.py` for executable examples.
