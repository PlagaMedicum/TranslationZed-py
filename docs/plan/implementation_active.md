# Active Implementation Plan

_Updated: 2026-06-23_

## Current Objective

Close the v0.9.0 release from the current worktree without reopening product scope.

The documentation and agent-surface cleanup is complete: current contracts remain available,
completed packet logs have moved out of normal context, active risks are explicit, and generated
source context is now targeted and on demand.

The remaining release sequence is:

1. verify the integrated code and documentation worktree;
2. run `make release-evidence-check` to identify stale or missing interactive evidence;
3. rerun only the manual scenarios reported by that checker;
4. sync fresh passed evidence through the supported release-evidence commands;
5. run the release gate for the intended tag.

## Constraints

- Treat existing uncommitted product and manual-framework changes as intentional baseline work.
- Do not add features or perform broad runtime cleanup during release closure.
- Preserve deterministic behavior, byte-exact save structure, no-write-on-open safety, locale
  encoding fidelity, security boundaries, and performance budgets.
- Source-reference behavior is requested locale or empty Source cells when the matching file is
  absent.
- `TZP_STATUS_COMMENT_PREFIX` is not a user-facing preference.
- Current-file encoding remains visible while a file is open.
- Interactive release evidence is human-owned. Do not fabricate or hand-edit evidence that should
  come from a passed interactive run.
- Reproduce benchmark failures in the intended workflow before changing code or baselines.

## Verified State

For the documentation and agent-surface cleanup on 2026-06-23:

- `make docs-check` passes;
- `make gate-dev` passes;
- focused documentation, contract-context, and gate-policy tests pass;
- `git diff --check` passes;
- `README.md` is unchanged.

This does not assert that interactive release evidence or the full release gate is current. Run the
corresponding commands for authoritative status.

## Acceptance Criteria

- Machine-owned release gates pass on the intended release commit.
- `make release-evidence-check` passes using fresh interactive evidence.
- Required manual scenarios use real application actions and their documented finish conditions.
- Version, changelog, packaging, benchmark, and release metadata checks agree with the intended tag.
- No unrelated feature or architecture expansion is introduced during blocker closure.

## Open Follow-ups

- Runtime simplification requires a separate behavior-preserving plan after release closure.
- Reassess Make/CI command complexity separately; the current documentation pass intentionally did
  not remove general test, performance, security, packaging, or release machinery.
