# TranslationZed-Py — Performance Math Appendix
_Last updated: 2026-02-24_

## 1) Purpose

This appendix defines math-backed performance contracts for parser/TM optimization.
It is intentionally deeper than canonical feature docs and serves as a
proof-oriented reference when optimizing hot paths.

Normative behavior remains in:
- `docs/translation_zed_py_technical_specification.md`
- `docs/testing_strategy.md`
- `docs/implementation_plan.md`

## 2) Parser Model

For one parse operation:

\[
T_{\text{parse}} = T_{\text{tokenize}} + T_{\text{offset}} + T_{\text{finalize}}
\]

where:
- \(T_{\text{tokenize}}\): lexical scanning / token classification,
- \(T_{\text{offset}}\): char→byte offset map construction,
- \(T_{\text{finalize}}\): entry assembly and status extraction.

### 2.1 Amdahl Derivation For 45% Total Speedup

Target total factor (faster is smaller) is:

\[
F = 0.55
\]

If improved fraction is \(p\), and component speedup is \(S\):

\[
F = (1-p) + \frac{p}{S}
\]

Solve for required component speedup:

\[
S_{\text{required}} = \frac{p}{F - (1-p)}
\]

Example with \(p=0.70\):

\[
S_{\text{required}} = \frac{0.70}{0.55 - 0.30} = 2.8
\]

So the optimized component must be roughly \(2.8\times\) faster.

### 2.2 Offset Mapping Complexity Contract

Given \(n\) Unicode code points:
- legacy incremental-encoder path: \(\Theta(n)\) encoder calls,
- UTF-8 fast path: \(\Theta(n)\) branch-only code-point width accumulation,
- UTF-16 fast path: \(\Theta(n)\) surrogate-width accumulation,
- single-byte fast path: \(\Theta(n)\) arithmetic progression.

Fast paths are admissible only if they satisfy:

\[
\forall i \in [0,n-1]:\;\Delta_i = \text{offset}[i+1]-\text{offset}[i] = |\text{encode}(c_i)|
\]

and

\[
\text{offset}[0]=0,\quad \text{offset}[n]=|\text{raw-bytes-without-BOM}|
\]

Fallback obligation: if a fast-path estimate violates final byte-length equality,
legacy mapping is recomputed; mismatch after fallback is a hard parse error.

## 3) TM Query Model

Per query:

\[
T_{\text{tm}} = T_{\text{sql}} + N_c\left(T_{\text{ratio}} + T_{\text{token}} + T_{\text{phrase}} + T_{\text{overlap}}\right)
\]

where \(N_c\) is candidate count after SQL retrieval/dedup.

Optimization constraints (no scoring drift):
- ranking/scoring formula is unchanged,
- improvements are only from computation reuse (token/stem/phrase caches,
  reduced repeated tokenization/stemming),
- output order and score are bit-stable for fixed corpus/query packs.

## 4) Cache-Cap Invariants

For each cache \(C_j\) with capacity \(K_j\):

\[
|C_j(t)| \le K_j\quad\forall t
\]

with deterministic LRU eviction. Current caps:
- token cache: `8192`
- stem cache: `4096`
- phrase cache: `2048`
- token-match cache: `8192`

Amortized operations are \(O(1)\) for get/put and bounded-memory by design.

## 5) Search Wave-2 Cost Model

Legacy model:

\[
T_{\text{search-old}} \approx N_{\text{rows}}(C_{\text{lower}} + C_{\text{query-split}} + C_{\text{match}})
\]

Hoisted model:

\[
T_{\text{search-new}} \approx N_{\text{rows}}(C_{\text{lower}} + C_{\text{match}}) + C_{\text{query-split}}
\]

This is valid only if literal/regex/case result sets remain invariant.

## 6) Statistical Measurement Contract

Single-shot timings are disallowed for gates. We use repeated timing and robust
estimators:

Median:

\[
\tilde{x} = \operatorname{median}(x_1,\dots,x_n)
\]

Median absolute deviation (MAD):

\[
\operatorname{MAD} = \operatorname{median}\left(|x_i - \tilde{x}|\right)
\]

Speed gain (percentage):

\[
G = 100\cdot\frac{\tilde{x}_{\text{legacy}}-\tilde{x}_{\text{new}}}{\tilde{x}_{\text{legacy}}}
\]

Confidence reporting uses bootstrap median intervals:
- resample with replacement,
- compute bootstrap medians,
- report 2.5% and 97.5% quantiles.

## 7) Equivalence Proof Obligations

### 7.1 Parser

Optimized parser must preserve:
1. key/value/status sequence,
2. byte spans and segment boundaries,
3. concat gap bytes,
4. malformed-but-supported parse behavior.

### 7.2 TM

For fixed corpora/query packs, optimized TM must preserve:
1. result count under same limits/thresholds,
2. exact score values,
3. ordering (including tie-break paths).

## 8) Dependency Trust Gate

A performance dependency is admissible only if all pass:
1. license compatibility,
2. mature maintained upstream,
3. Python 3.10+ cross-platform compatibility,
4. no hidden runtime/network side effects,
5. measured gain `>15%` over optimized pure-Python baseline,
6. bit-stable equivalence for locked contracts.

Any failed condition yields explicit rejection with evidence.
