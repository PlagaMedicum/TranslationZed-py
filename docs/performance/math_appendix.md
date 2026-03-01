# TranslationZed-Py — Performance Math Appendix
_Last updated: 2026-02-25_

## 1) Purpose

This appendix defines math-backed performance contracts for parser/TM/search
optimization work. It is proof-oriented and intentionally deeper than feature docs.

Canonical behavior remains in:
- `docs/spec/technical.md`
- `docs/quality/testing_strategy.md`
- `docs/plan/implementation_active.md`

## 2) Notation Legend

| Symbol | Meaning |
|---|---|
| $T_{x}$ | Runtime cost of component $x$ |
| $F$ | Target total runtime factor relative to baseline |
| $p$ | Fraction of runtime attributable to optimized component |
| $S$ | Component-level speedup factor |
| $N_c$ | Number of TM candidates after retrieval/dedup |
| $\tilde{x}$ | Sample median |
| $\operatorname{MAD}$ | Median absolute deviation |

## 3) Parser Model

For a single parse operation:

$$
T_{\text{parse}} = T_{\text{tokenize}} + T_{\text{offset}} + T_{\text{finalize}}
$$

where:

- $T_{\text{tokenize}}$: lexical scanning/token classification,
- $T_{\text{offset}}$: char-to-byte offset map construction,
- $T_{\text{finalize}}$: entry assembly and status extraction.

### 3.1 Amdahl Derivation For 45% Total Speedup

Target total factor:

$$
F = 0.55
$$

Amdahl relation:

$$
F = (1-p) + \frac{p}{S}
$$

Required component speedup:

$$
S_{\text{required}} = \frac{p}{F - (1-p)}
$$

Example for $p=0.70$:

$$
S_{\text{required}} = \frac{0.70}{0.55 - 0.30} = 2.8
$$

### 3.2 Offset Mapping Equivalence Contract

Given $n$ Unicode code points:

- legacy incremental encoder path: $\Theta(n)$ encoder calls,
- UTF-8 fast path: $\Theta(n)$ branch-only width accumulation,
- UTF-16 fast path: $\Theta(n)$ surrogate-width accumulation,
- single-byte fast path: $\Theta(n)$ arithmetic progression.

Fast paths are admissible only if:

$$
\forall i \in [0,n-1]:\;\Delta_i = \text{offset}[i+1]-\text{offset}[i] = |\text{encode}(c_i)|
$$

and:

$$
\text{offset}[0]=0,\quad \text{offset}[n]=|\text{raw-bytes-without-BOM}|
$$

Fallback obligation: if fast-path estimate violates final byte-length equality,
recompute with legacy path; mismatch after fallback is a hard parse error.

## 4) TM Query Cost Model

Per query:

$$
T_{\text{tm}} = T_{\text{sql}} + N_c\left(T_{\text{ratio}} + T_{\text{token}} + T_{\text{phrase}} + T_{\text{overlap}}\right)
$$

Optimization constraints:

1. ranking/scoring formula unchanged,
2. improvements from computation reuse only,
3. ordered scores remain bit-stable for fixed corpus/query packs.

### 4.1 Warm/Cold Cache Decomposition

Define:

- $T_{\text{cold}}$: first-pass latency with empty caches,
- $T_{\text{warm}}$: steady-state latency with warm caches,
- $h \in [0,1]$: effective warm-hit share within session.

Expected latency:

$$
\mathbb{E}[T_{\text{tm}}] = (1-h)T_{\text{cold}} + hT_{\text{warm}}
$$

Relative gain over legacy baseline $T_{\text{legacy}}$:

$$
G(h) = 1 - \frac{(1-h)T_{\text{cold}} + hT_{\text{warm}}}{T_{\text{legacy}}}
$$

## 5) Cache-Cap Invariants

For each bounded cache $C_j$ with cap $K_j$:

$$
|C_j(t)| \le K_j\quad \forall t
$$

Current caps:

- token cache: `8192`
- stem cache: `4096`
- phrase cache: `2048`
- token-match cache: `8192`
- query-result cache: `256`

## 6) Search Wave-2 Cost Model

Legacy model:

$$
T_{\text{search-old}} \approx N_{\text{rows}}(C_{\text{lower}} + C_{\text{query-split}} + C_{\text{match}})
$$

Hoisted decomposition model:

$$
T_{\text{search-new}} \approx N_{\text{rows}}(C_{\text{lower}} + C_{\text{match}}) + C_{\text{query-split}}
$$

This optimization is valid only if literal/regex/case match sets remain invariant.

Current implementation note:

- In no-preview literal scans (`include_preview=false`), the row loop now uses
  a direct boolean predicate path (`_matches_literal`) instead of tuple-return
  index probing. This removes per-row tuple allocation on the non-hit path and
  improves packed-query median latency stability.

Wave-2 strict gate:

$$
G_{\text{search}} =
100\cdot\frac{\tilde{x}^{(\mathrm{legacy})}-\tilde{x}^{(\mathrm{new})}}
{\tilde{x}^{(\mathrm{legacy})}}
\ge 30\%
$$

where the default threshold is enforced by
`TZP_PERF_SEARCH_SPEEDUP_20K_PERCENT=30` in `tests/test_search_perf_contract.py`.

## 7) Statistical Measurement Contract

Single-shot timings are invalid for gates.

Median:

$$
\tilde{x} = \operatorname{median}(x_1,\dots,x_n)
$$

MAD:

$$
\operatorname{MAD} = \operatorname{median}\left(|x_i - \tilde{x}|\right)
$$

Speed gain percentage:

$$
G = 100\cdot\frac{\tilde{x}^{(\mathrm{legacy})}-\tilde{x}^{(\mathrm{new})}}{\tilde{x}^{(\mathrm{legacy})}}
$$

Confidence reporting uses bootstrap median intervals (2.5%, 97.5% quantiles).

## 8) Equivalence Proof Obligations

### 8.1 Parser

Optimized parser must preserve:

1. key/value/status sequence,
2. byte spans and segment boundaries,
3. concat gap bytes,
4. malformed-but-supported parsing behavior.

### 8.2 TM

For fixed corpora/query packs, optimized TM must preserve:

1. result count under same thresholds/limits,
2. exact score values,
3. ordering including tie-break behavior.

## 9) Dependency Trust Gate

A performance dependency is admissible only if all conditions pass:

1. license compatibility,
2. mature maintained upstream,
3. Python 3.10+ cross-platform support,
4. no hidden runtime/network side effects,
5. measured gain $>15\%$ over optimized pure-Python baseline,
6. zero drift on locked equivalence contracts.
