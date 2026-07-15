# Documentation Structure

This page routes contributors and agents to the smallest authoritative context for a task.
Document count is not a quality target; clear ownership and low synchronization cost are.

## Authority By Question

| Question | Canonical owner |
|---|---|
| What does the application do technically? | `docs/spec/technical.md` |
| What does the user observe or decide? | `docs/ux/use_cases.md` and its workflow pages |
| Where does code and policy belong? | `docs/architecture/overview.md` and `code_architecture.md` |
| How does a non-obvious algorithm work? | `docs/domain/` or `docs/performance/` |
| How is behavior verified? | `docs/quality/testing_strategy.md` |
| Which command should be run? | `docs/reference/automation_surface.md` |
| Which tests cover a workflow? | `docs/reference/test_surface.md` |
| Which module owns a responsibility? | `docs/reference/module_map.md` |
| What work is active now? | `docs/plan/implementation_active.md` |
| Why was a durable decision made? | `docs/plan/implementation_history.md` |
| Which modules require extra care? | `docs/reference/risk_register.md` |

`docs/reference/quick_context.md` is the normal entrypoint for human and LLM orientation.
`docs/index.md` is the browser documentation index.

## Document Lifecycles

### Current contracts

Technical, UX, architecture, domain, performance, and testing documents describe current truth.
Version-specific feature documents may remain when they contain useful schemas, formulas, state
machines, compatibility rules, or failure semantics. Once implemented, they must be described as
current contracts rather than future plans.

### Active work

`docs/plan/implementation_active.md` contains only the current objective, slice status, constraints,
acceptance criteria, verified state, unresolved decisions, and open follow-ups. Completed packet
narratives do not remain there.

While a release is under development, version-specific planned contracts may live under
`docs/spec/<version>/` when clearly labeled as planned and linked from the active plan. They do not
override current technical or UX contracts. Promote their implemented behavior to the canonical
owners as each slice closes.

### Durable history

`docs/plan/implementation_history.md` is a compact decision and lessons ledger. Detailed execution
logs remain available in git history and should not be copied into normal agent context.

### Generated and on-demand references

Generated source indexes are disposable navigation aids, not canonical behavior. Generate targeted
contract context with `scripts/generate_contract_index.py`; do not commit a full-repository index.
API pages are rendered from current source by the documentation build.

## Update Rules

1. Update the canonical owner when behavior, an interface, an invariant, or an operator workflow
   changes.
2. Update a summary or index only when the change makes that summary inaccurate.
3. Do not repeat normative details merely to satisfy a synchronization checklist; link instead.
4. Put detailed algorithms and proof obligations in focused domain/performance documents rather
   than inflating overview pages.
5. Record a decision in the history ledger only when future work needs its rationale or constraint.
6. Add an active risk only when it changes how a contributor should modify or verify a module.
7. Keep questionable implementation factual. Do not use documentation to declare risky code safe.
8. Preserve machine checks for safety invariants, formulas, API/module coverage, commands, and gate
   parity; avoid checks that merely require exact prose or duplicate milestone text.

If documents disagree, the owner in the table above wins for its question. Resolve the conflict at
the source instead of adding another precedence layer.
