# TM Quality And Explainability Contract
_Updated: 2026-06-23_

## 1) Purpose

Define score explainability and deterministic ranking guarantees for TM suggestions.

## 2) Preserved Scoring Core (Normative)

Raw score:

$$
raw = \operatorname{round}(100 \cdot ratio)
$$

Final score before caps:

$$
score_0 = \min(100, raw + token\_bonus)
$$

Composed-phrase floor (multi-token):

$$
score_1 = \max(score_0, 90)
$$

Exact/fuzzy cap rule:
- if non-exact candidate reaches 100, clamp to 99.

## 3) Retrieval/Gate Formulas (Referenced)

Base length band:

$$
L_{\min\_base} = \max(1, \lfloor 0.6 L_q \rfloor)
$$

$$
L_{\max\_base} =
\begin{cases}
\lfloor 1.4 L_q \rfloor, & L_q > 5 \\
L_q + 10, & \text{otherwise}
\end{cases}
$$

Long multi-token trigger:

$$
is\_long\_multi := (k \ge 8) \land (L_q \ge 80)
$$

Adaptive upper bound:

$$
L_{\max} = \max(L_{\max\_base}, \lfloor 1.85 L_q \rfloor)
$$

Oversized guard for $L_c > L_{\max\_base}$:

$$
overlap \ge 0.55 \;\lor\; (composed\_phrase \land ratio \ge 0.70)
$$

## 4) Explainability Payload Schema

```text
TMExplainability {
  score: int,
  raw_score: int,
  ratio: float,
  overlap: float,
  exact_overlap: float,
  token_bonus: int,
  composed_phrase: bool,
  long_multi_triggered: bool,
  band: {
    min_base: int,
    max_base: int,
    min_effective: int,
    max_effective: int
  },
  oversized_guard_applied: bool,
  oversized_guard_passed: bool|null,
  cap_reason: "none"|"fuzzy_to_99"|"composed_floor",
  tie_break: {
    token_count_delta: int,
    origin_priority: int,
    updated_at: int
  },
  decision_notes: list[str]
}
```

## 5) Determinism Guarantees

1. Existing ranking order and score values must remain compatible with current corpus contracts.
2. Explainability payload is diagnostic metadata and must not alter ranking decisions.
3. Tie-break order remains stable for identical inputs.

## 6) Complexity and Cache Notes

Expected query cost model:

$$
T_{tm} = T_{sql} + N_c\big(T_{ratio}+T_{token}+T_{phrase}+T_{overlap}\big)
$$

Explainability overhead constraint:

$$
\Delta T_{explain} \le 0.1 \cdot T_{tm}\;\text{(target envelope)}
$$

Caching policy remains bounded and deterministic.

## 7) UI Explanation Contract

The selected TM suggestion must provide:
1. Why it matched (ratio/overlap/token/composed factors).
2. Why it scored as shown (raw->bonus->caps path).
3. Why it ranked above/below neighbors (tie-break factors).

## 8) Acceptance Scenarios

1. Exact match:
   - score 100,
   - explainability reports exact path.
2. Long edited variant:
   - visible at default threshold,
   - explainability shows adaptive-band trigger and guard path.
3. Oversized noisy candidate:
   - rejected with explicit guard reason.
4. Ranking tie:
   - deterministic tie-break reasons shown.
