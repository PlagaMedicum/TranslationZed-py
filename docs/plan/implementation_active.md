# Active Implementation Plan

_Updated: 2026-06-23_

## Current Objective

Prepare and close the unreleased v0.9.0 release without reopening product scope.

The documentation and agent-surface cleanup is complete: current contracts remain available,
completed packet logs have moved out of normal context, active risks are explicit, and generated
source context is now targeted and on demand.

The remaining release sequence is:

1. freeze a clean release-candidate commit and record its SHA;
2. run the machine-owned preflight, including `make gate-ci-pr`, benchmark checks, and
   `make release-check TAG=v0.9.0`;
3. run `make release-evidence-check` and rerun every manual scenario it reports as missing,
   stale, or structurally outdated;
4. sync only fresh passed evidence through the supported release-evidence commands;
5. review the tracked evidence diff, commit it without unrelated changes, and record the resulting
   release commit SHA;
6. from that clean commit, rerun `make release-evidence-check` and
   `make gate-release TAG=v0.9.0`;
7. tag that exact commit, push the tag, and verify the release workflow's Linux, macOS, and Windows
   package builds, smoke runs, uploaded archives, and draft release.

## Constraints

- Preserve any user work that appears during closure; do not fold unrelated changes into release
  fixes or evidence commits.
- Do not add features or perform broad runtime cleanup during release closure.
- Change runtime code only for a reproduced release blocker, using the smallest behavior-preserving
  fix and focused regression coverage.
- Preserve deterministic behavior, byte-exact save structure, no-write-on-open safety, locale
  encoding fidelity, security boundaries, and performance budgets.
- Source-reference behavior is requested locale or empty Source cells when the matching file is
  absent.
- `TZP_STATUS_COMMENT_PREFIX` is not a user-facing preference.
- Current-file encoding remains visible while a file is open.
- Interactive release evidence is human-owned. Do not fabricate or hand-edit evidence that should
  come from a passed interactive run.
- Reproduce benchmark failures in the intended workflow before changing code or baselines.
- Do not create or push the release tag until the exact tagged commit is clean and passes the local
  release gate.

## Verified State

For the documentation and agent-surface cleanup on 2026-06-23:

- `make docs-check` passes;
- `make gate-dev` passes;
- focused documentation, contract-context, and gate-policy tests pass;
- `git diff --check` passes;
- `README.md` is unchanged.

This does not assert that interactive release evidence or the full release gate is current. Run the
corresponding commands for authoritative status.

Current release checks on 2026-06-23:

- `make gate-ci-pr` passes after focused session-resume persistence and malformed-payload coverage
  closed the strict coverage blocker;
- strict coverage is 92.1% whole-package and 97.4% core;
- `make bench-check` passes the Linux benchmark regression comparison;
- `make release-check TAG=v0.9.0` passes version and changelog alignment;
- no `v0.9.0` or v0.9.0 release-candidate tag exists at the current commit;
- `make release-evidence-check` reports that all ten required manual scenarios need fresh runs:
  seven are missing and the three existing records are stale or structurally outdated.

## Acceptance Criteria

- Machine-owned release gates pass on the intended release commit.
- `make release-evidence-check` passes using fresh interactive evidence.
- Required manual scenarios use real application actions and their documented finish conditions.
- The release commit is clean, its SHA is recorded, and the release tag points to that exact commit.
- Version, changelog, benchmark, and release metadata checks agree with `v0.9.0`.
- Linux, macOS, and Windows release packages build, pass their workflow smoke runs, upload
  successfully, and appear on the draft release.
- No unrelated feature or architecture expansion is introduced during blocker closure.

## Open Follow-ups

- Runtime simplification requires a separate behavior-preserving plan after release closure.
- Reassess Make/CI command complexity separately; the current documentation pass intentionally did
  not remove general test, performance, security, packaging, or release machinery.
