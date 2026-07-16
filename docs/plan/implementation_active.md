# Active Implementation Plan

_Updated: 2026-07-16_

## Current Objective

Deliver v1.0.0 from `dev`, starting at the exact v0.9.0 release commit, without weakening
lossless editing, cache-first safety, deterministic behavior, encoding fidelity, or bounded
resource use.

The scope index is `docs/spec/v1_0/overview.md`; implementation order, failure semantics, and
per-slice proof obligations are owned by `docs/spec/v1_0/delivery_plan.md`. Current technical and
UX contracts describe implemented behavior only.

## Slice Status

| Slice | State | Current boundary |
|---|---|---|
| Planning contract | Complete | User intent, ordering, non-goals, and acceptance are documented. |
| Reliability prerequisite | Complete | Project sessions are one-writer, stale locks activate real draft recovery, session snapshots are atomic, rotating logs and copyable issue reports exist, and unexpected Python GUI exceptions are contained and reported. |
| 0. PZ B42.15+ format compatibility ([Issue #1](https://github.com/PlagaMedicum/TranslationZed-py/issues/1)) | Complete | The B42.19 flat JSON contract is implemented for discovery, existing-key editing, cache/session identity, recovery, search, QA, TM, Git path inspection, source reference, and atomic Save. Automated gates, the 13k-row budget, and the interactive roundtrip pass. Keep the issue open until the v1.0.0 release by user decision. |
| 1. Git synchronization | Foundation only | Read-only Git/ref/blob inspection and baseline-state primitives exist with focused tests. Change classification, merge policy, UI, and startup/save integration do not. |
| 2. Add localization | Foundation only | Staged clone policy and chooser/warning dialogs exist with focused tests. Treat them as retained scaffold, not a finished workflow. |
| 3. `description.txt` | Complete — existing behavior accepted | The generic raw-file path already presents keyless content as one normal table/detail row. Do not add a separate editor, parser, model, or workflow; only presentation-only file-tree polish may be considered during release coherence. |
| 4. QA safety pack | Not started | Existing v0.9 QA remains current. |
| 5. LanguageTool extension | Not started | Existing v0.9 LanguageTool behavior remains current. |
| 6. Machine translation | Not started | v1 requires provider-neutral conventional MT plus context-aware local LLM adapters for Ollama and llama.cpp-compatible servers. |
| 7. Release closure | Not started | Begin only after slices 0–6 meet their acceptance gates. |

## Constraints

- Work on `dev`; integrate the exact clean release commit into `main` only at final closure.
- Git integration is read-only: never fetch, pull, stage, commit, or change branches.
- Detection, synchronization, and project open never write original locale files.
- Preserve legacy `.txt` support while adding only confirmed B42.15+ format variants. Do not infer
  a JSON schema from filenames, third-party converters, or the issue description alone.
- Preserve translations when EN text changes; marking `For review` is explicit.
- Locale creation does not own `description.txt`; keep the accepted generic raw-file behavior.
- Machine translation is optional, never auto-applied, and marked `For review` when accepted.
- Preserve both requested v1 provider classes: conventional non-LLM machine translation and a
  context-aware local LLM. Conventional MT must not be designed around Google or any other single
  vendor; Google may be one documented adapter, not the privileged or exclusive path.
- Support both Ollama and llama.cpp-compatible HTTP servers for the local LLM path. Do not bundle,
  start, download, or manage either runtime or its models.
- Keep Qt in GUI adapters and workflow/provider policy in Qt-free core modules.
- Refactor only to remove proven duplication or enforce a boundary used by the active slice.
- Preserve v0.9 settings, caches, snapshots, TM databases, and session state.

## Verified State

- `dev` is fast-forwarded to tagged commit `v0.9.0` (`45baa879a09656338cfab029616af7b3d4d68386`).
- The v0.9.0 worktree was clean before v1 work began.
- v0.9.0 provides snapshot-based `NEW/MODIFIED/REMOVED` detection, comment-preserving NEW-row
  insertion, conflict resolution, QA/LT, TM, and strict multi-platform release gates.
- Issue #1 contains two independent reports. v0.9.0 includes the malformed-`language.txt` warning
  that fixes the silent-abort symptom; `dev` adds a specific no-valid-target message and implements
  the confirmed B42.19 JSON editing boundary. Slice 0 is complete, but keep the issue open until the
  v1.0.0 release by user decision.
- Read-only inspection of the local B42.19 installation confirmed 610 flat UTF-8 string-map JSON
  files and all 1,192,196 entries parsed successfully. Exact provenance and hashes are recorded in
  `docs/domain/b42_json_format.md`; only synthetic fixtures are committed.
- The observed BE game directory still contains legacy translation payloads rather than BE JSON.
  B42 can therefore list/select the locale from `language.txt` without having JSON translations to
  display. Application support does not implicitly convert those files.
- No runtime Git synchronization, locale creation, or MT provider existed at the v1 baseline.
  `description.txt` needs no specialization: its existing generic raw-file table behavior is the
  accepted result. The status table above is the authority for work added since that baseline.
- The retained foundation, reliability prerequisite, and planning work pass
  `make gate-task-close` on 2026-07-15 (92.2% overall coverage, 97.2% core). This is verified
  infrastructure/scaffold evidence, not completion of Slice 0 or later feature slices.
- Slice 0 task-close component lanes pass on 2026-07-16: commit/push checks, 210-test core
  baseline, changed-file routed suites, read-only diagnostics, docs, scale performance, and full
  branch coverage (92.26% overall, 97.02% core). Interactive scenario
  `b42-json-open-edit-save` passed and its release evidence was synced on 2026-07-16.

## Acceptance Criteria

- Every slice has focused core, GUI, failure-path, and performance coverage proportional to risk.
- Confirmed B42.15+ fixtures open, edit, cache, recover, search, QA, TM-index, and save without
  weakening legacy `.txt`, byte/encoding, atomic-write, or no-write-on-open behavior.
- Git synchronization is deterministic, previewed, cancellable, and cache-only until Save.
- Locale creation warns about official community coordination and never overwrites a locale.
- Preserve the accepted generic single-row `description.txt` behavior; do not introduce a
  specialized editing path.
- QA/LT/MT remain asynchronous or bounded where applicable and discard stale results.
- Conventional MT and both local-LLM protocols are fakeable in tests and remain visually separate
  from ranked TM data.
- `make gate-ci-pr`, strict benchmarks, fresh interactive evidence, and
  `make gate-release TAG=v1.0.0` pass on the exact clean release commit.
- The final tag triggers successful Linux, macOS, and Windows packages and smoke runs.

## Open Follow-ups

- User-defined QA rule files, updater/PR integration, and automatic background MT generation remain
  v1.1-or-later work.
- Theme expansion is not planned.
- Any `description.txt` file-tree presentation improvement belongs to Slice 7 UI coherence and must
  not create format-specific editing logic.
- Direct final release is intentional; no release-candidate workflow is required for v1.0.0.

## Confirmed Slice 6 Provider Direction

- Conventional MT uses a provider-neutral core contract and documented, licensed interfaces only.
  No unofficial web scraping or Google-specific request model may define the shared interface.
- Google Translate may be offered through an official adapter, alongside non-Google conventional
  providers. The concrete adapter roster must be selected from documented interfaces before
  implementation and recorded in the slice change; provider diversity is required for v1.
- Context-aware local generation supports user-managed Ollama and llama.cpp-compatible HTTP
  servers through separate adapters. Endpoints and models are explicit user configuration; the
  application remains usable when neither runtime is installed.
