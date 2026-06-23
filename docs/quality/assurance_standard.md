# Assurance Standard

## Purpose

Keep changes reviewable and evidence-based without turning documentation into a second
implementation.

## Change Standard

1. Identify the behavior, interface, invariant, or failure mode being changed.
2. Read its canonical owner from `docs/meta/docs_structure.md`.
3. Make the smallest coherent code and documentation change.
4. Add or update tests for changed behavior and costly failure modes.
5. Run focused verification first, then broaden according to risk.
6. Report environment limitations and unresolved failures explicitly.

Do not normalize questionable implementation through documentation. State current behavior and
risk factually; do not claim that code is safe merely because it is documented.

## Active Risks

`docs/reference/risk_register.json` lists modules that require special care. Entries contain:

- the module path;
- the concrete concern;
- constraints that must survive changes;
- focused regression tests;
- severity.

The register contains active risks only. Completed refactor history belongs in git; durable lessons
belong in tests, code comments, architecture documents, or the decision ledger.

Changed application modules are triaged during `make docs-check`. Size, function length, and branch
density are risk-discovery signals rather than refactoring commands. A changed module that crosses
a high-risk threshold must have an active register entry with concrete constraints and tests.

## Documentation Standard

- Document public interfaces, architecture boundaries, invariants, compatibility requirements,
  failure modes, algorithms, and hard-won operational lessons.
- Keep ordinary code self-explanatory.
- Link to a canonical owner instead of copying normative detail.
- Generated API and source indexes are navigation aids, not behavior authorities.
- Documentation checks validate structure, links, navigation, buildability, documented command
  existence, gate-policy parity, module/API coverage, current lifecycle wording, and preservation
  of selected safety/formula contracts.
- Semantic checks protect important ideas and interfaces; they must not prescribe ordinary prose
  or require duplicated milestone narratives.

## Completion Standard

Before completion:

- run the narrowest tests covering changed behavior;
- run formatting, lint, type, architecture, and documentation checks appropriate to the surface;
- run `git diff --check`;
- inspect the final diff for unrelated edits and accidental generated artifacts.

Release, benchmark, and interactive manual evidence must come from their real workflows. Do not
edit evidence merely to satisfy a gate.
