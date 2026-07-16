# v1.0 Detailed Delivery Plan

_Status: active · updated 2026-07-16_

This document is the implementation handoff for v1.0. It orders work into independently reviewable
slices. A slice is complete only when its behavior, focused tests, performance evidence, and
canonical documentation agree. Do not begin a later slice by weakening an earlier safety contract.

## 1. Delivery Rules

- Develop on `dev`, which starts at the exact `v0.9.0` commit. Do not mix v1 feature work into the
  tagged release or unrelated cleanup.
- Start every slice with its Qt-free policy/data model. Add GUI wiring only after core behavior and
  failure semantics are executable in tests.
- Preserve no-write-on-open, cache-first drafts, explicit original-file writes, atomic replacement,
  locale-declared encoding, byte-exact structure outside intentional mutations, deterministic
  ordering, and bounded memory/work.
- Prefer one direct owner for each decision. Add an interface only when it isolates filesystem,
  Git, network, provider, or GUI effects for real tests.
- Run the narrowest tests during implementation. Close every slice with `make gate-task-close`,
  `make docs-check`, relevant performance checks, and `git diff --check`.
- Do not promote planned text into current technical or UX contracts until the implementation and
  tests are complete.
- Complete Slice 0 before implementing format-dependent Git synchronization, QA, LT, TM, or MT
  integration. Those slices must consume one confirmed file-format boundary
  rather than independently assuming legacy `.txt` syntax.

## 2. Slice 0 — PZ B42.15+ Format Compatibility (Release Blocker)

### Intent and evidence status

Resolve the remaining compatibility part of
[Issue #1](https://github.com/PlagaMedicum/TranslationZed-py/issues/1) before building other v1
features on a `.txt`-only model. The issue has two parts:

1. v0.9.0 already shows malformed-`language.txt` details instead of silently aborting; `dev` also
   gives the all-invalid/no-target case its own actionable message.
2. JSON compatibility was open at the v1 baseline. `dev` now has the dual-format implementation;
   task-close component lanes and the synced interactive roundtrip are green. Issue #1 remains open
   until the v1.0.0 release by user decision.

Do not derive a production schema solely from the issue report. As of 2026-07-15, the
[official community translation repository](https://github.com/TheIndieStone/ProjectZomboidTranslations)
still exposes the legacy locale tree, so implementation starts with an authoritative B42.15+
game fixture, official schema/source, or maintainer-confirmed sample and records its provenance.
The discovery gate is now satisfied by a read-only B42.19.0 installed corpus. The detailed evidence,
accepted schema, preservation rules, and unsupported boundary are canonical in
`docs/domain/b42_json_format.md`; committed fixtures contain synthetic strings only.

The implemented boundary edits existing flat JSON string-map keys. It deliberately does not
convert legacy translation files or insert missing JSON keys. Format-aware new-key insertion is a
Slice 1 requirement and must not reuse the legacy line-insertion algorithm.

### Discovery gate

1. Capture the smallest legally redistributable fixtures, or schema-only synthetic fixtures with
   hashes/field notes when game files cannot be committed. Record filename rules, object/array
   shape, key/value types, ordering significance, escaping, line endings, BOM/encoding behavior,
   nesting, metadata, and whether comments or duplicate keys can occur.
2. Determine whether JSON replaces every legacy file, only named families, or coexists with
   `.txt`; define deterministic discovery and collision behavior for two files representing the
   same logical content.
3. Reject the slice if the evidence is insufficient. An explicit unsupported-format error is safer
   than a permissive parser that can rewrite unknown data.

### Core and workflow work

1. Replace the single-extension assumption at the scanner/parser/saver boundary with a small
   format-dispatch contract. Keep the proven legacy parser/saver unchanged behind that boundary;
   do not force conversion between formats.
2. Implement the confirmed JSON variant with deterministic ordering, strict shape/type validation,
   bounded parsing, and atomic value-only writes. Preserve all structure the confirmed format
   permits outside intentional value edits; never silently collapse duplicate or unknown data.
3. Include format identity in cache/session/EN-diff/Git-sync identities so same-named legacy and
   JSON files cannot share stale drafts or baselines.
4. Route both formats through the implemented open/edit/status/undo, cache recovery,
   search/replace, QA, LT, TM, source-reference, explicit Save, and conflict paths. Planned MT must
   consume the same row/document view when Slice 6 implements it; Slice 0 does not invent an MT
   adapter. Format-specific rules stay in core.
5. Show actionable errors for malformed or unsupported JSON and for projects with no supported
   target files. Opening, previewing, or failing format detection never changes locale originals.

### Failure and acceptance cases

- Cover malformed/truncated payloads, duplicate keys, unexpected scalar/container types, unknown
  fields, escaping and Unicode edges, BOM/EOL variants confirmed by evidence, mixed projects,
  logical-name collisions, read-only files, interrupted atomic replacement, huge values, and
  cancellation/reopen recovery.
- Prove legacy `.txt` parser/saver/encoding/roundtrip equivalence remains unchanged.
- Add representative JSON parse/save/search/cache benchmarks and one manual roundtrip scenario
  using the confirmed format. Slice closure requires no-write-on-open and byte/structure evidence,
  not merely successful `json.loads`/`json.dumps` roundtrips.

## 3. Slice 1 — Git-backed EN Synchronization

### Intent

Replace snapshot-only awareness with a repository-aware change range while retaining snapshot
fallback. TranslationZed-Py observes local committed history; it never manages Git for the user.

### Core work

1. Resolve the project worktree, user-selected baseline, and local `HEAD` through argument-list Git
   subprocesses with timeouts. Accept only commits and project-relative paths under `EN/`.
2. Persist a versioned project baseline under `.tzp/cache`. On first use, default to `HEAD` but
   permit an advanced ref/commit. Invalid or unreachable state produces a recovery choice, not
   mutation.
3. Read base/head blobs and classify per-file additions, deletions, renames, key order, source-value
   changes, and adjacent EN comment blocks.
4. Build an immutable merge plan per target locale/file. Decisions are `apply`, `ignore`, or
   `conflict`; cancellation produces no cache, snapshot, baseline, or original-file mutation.
5. For additions, stage target rows and EN comments in EN order. For modified sources, preserve the
   translation and offer `For review`. For removals, keep the existing marker-only behavior.
6. Treat comments as three-way data: replace EN-derived locale comments only when they equal the
   base EN block; otherwise require `keep locale` or `use EN`.
7. Advance the baseline only when every item is applied or explicitly ignored. Store unresolved
   work without falsely accepting `HEAD`.

### GUI and workflow

- Detect a changed committed `HEAD` during the existing startup EN check and expose
  `General → Synchronize from Git…` for explicit runs.
- Reuse conflict-workflow interaction patterns, but keep Git synchronization DTOs and policy
  separate from cache/original conflict DTOs.
- Preview files, keys, old/new source, comments, proposed status changes, and ignored items.
- Dirty EN worktree files are excluded from the committed range and shown as a warning.
- Applying a plan changes drafts/cache only. Normal Save remains the only route to originals.

### Failure and acceptance cases

- Cover missing Git, non-repository roots, nested project roots, initial/unborn repositories,
  shallow or pruned history, invalid refs, timeouts, malformed names, renames across EN boundary,
  binary/unreadable blobs, dirty/staged EN changes, cancellation, partial decisions, and retry.
- Use temporary real repositories for contract tests. Add large-change-set timing and memory caps.
- Add an interactive release scenario proving that additions/comments appear in the draft, changed
  translations remain unchanged, review marking is explicit, and original files remain unchanged
  until Save.

## 4. Slice 2 — Add Localization

### Intent

Create a new locale safely from the chooser while directing users to the official community process.
This slice does not own or depend on `description.txt` behavior.

### Community preflight

1. Before any creation fields or filesystem work, show a modal warning with:
   - the [official ProjectZomboidTranslations README](https://github.com/TheIndieStone/ProjectZomboidTranslations);
   - the [PZ Community Translations forum](https://theindiestone.com/forums/index.php?/forum/56-pz-community-translations/);
   - guidance to find and join an existing language effort or create a topic when none exists.
2. Continue remains disabled until the user acknowledges reading the README and checking the forum.
3. Open links through the system browser only. Do not scrape, query, or infer forum state. Browser
   failure shows the copyable URL and leaves the dialog open; Cancel is the default action.

### Creation workflow

1. Collect the clone source, new locale code, display name, and charset.
2. Reject empty or unsafe codes, separators, traversal, reserved/runtime directories, `EN`, and
   case-insensitive destination collisions.
3. Validate source locale metadata and target charset before writing.
4. Clone into a project-local staging directory. Keep `language.txt` metadata UTF-8 while rewriting
   only its new locale fields. Transcode other supported text from the source-declared charset when
   necessary, preserve line endings/text, and byte-copy unknown non-text files.
5. Publish by one directory rename. Any failure removes only the staging directory and leaves the
   source and destination untouched.
6. Rescan, add the locale to the open chooser as selected, seed compatible defaults, and preserve
   the current project/session state.

### Verification

- Test warning acknowledgment, both URLs, browser failure, validation, collisions, case variants,
  staging conflicts, decode/encode failures, rollback, metadata preservation, text transcoding,
  binary copying, rescan, and chooser selection.
- Add a manual scenario that inspects the new directory and proves no existing locale changed.

## 5. Slice 3 — `description.txt` As A Normal Row

### Accepted existing behavior

Closed by user decision on 2026-07-16. The generic raw-file path already opens a keyless file as one
normal table/detail entry and routes edits through the existing cache and explicit-Save behavior.
That is the intended KISS implementation.

Do not add a dedicated editor, parser, model, service, or locale-creation dependency for
`description.txt`. A presentation-only file-tree label or icon improvement may be considered in
Slice 7; it must not alter discovery, identity, parsing, caching, or saving. Add focused coverage
only if that presentation changes.

## 6. Slice 4 — Built-in QA Safety Pack

### Rules

- Extend protected-token comparison from missing-only to exact multiplicity, separately reporting
  missing and unexpected tags/placeholders.
- Add leading-boundary whitespace parity without duplicating the existing trailing rule.
- Flag NUL, disallowed control characters, and Unicode replacement characters.
- Detect duplicate keys at file scope without changing parser acceptance or save behavior.
- Keep all new rules opt-in compatible, individually persisted, deterministic, and low-noise. Do
  not add custom rule-file formats in v1.

### Integration and verification

- Extend rule IDs, labels, ordering, progress, summaries, grouping, result caps, navigation, stale
  suppression, and optional review marking through the existing QA service boundary.
- Test exact excerpts, severity/order, duplicates in lazy/eager files, per-rule disablement, large
  files, cancellation, background refresh, and edits that invalidate only affected findings.
- Benchmark the full local QA pack at existing representative sizes and preserve bounded results.

## 7. Slice 5 — LanguageTool Diagnostics And Assistance

### Technical diagnostics

- Add a Preferences action producing a copyable report for normalized endpoint, reachability,
  latency, configured language, level, picky fallback, response status, and actionable error.
- Keep HTTP security policy, timeout bounds, and offline isolation. A diagnostics run never changes
  text or QA state.

### Linguistic assistance

- Normalize and retain affected segment/context, message, rule ID, category, issue type, and bounded
  replacement proposals for every match.
- Present details from each underline/finding and apply replacements through the normal undoable
  edit path.
- Persist project-local accepted words and locale-scoped ignored rule IDs atomically. Accepted words
  filter only appropriate unknown-word findings; ignored rules filter by exact normalized rule ID.
- Refresh current findings after dictionary/ignore changes and discard stale async responses.

### Verification

- Test health success/offline/timeout/HTTP/malformed payload/picky fallback, proposal bounds, span
  validation, replacement undo/redo, dictionary scope, ignore scope, corrupted config recovery,
  concurrent checks, file switches, and shutdown.

## 8. Slice 6 — Machine Translation Providers

### Provider and data flow

1. Define Qt-free request, proposal, cache-key, provider diagnostic, and bounded local-context DTOs.
   Provider adapters must be directly fakeable and must not leak transport policy into TM ranking.
   This is a justified cohesive subpackage: keep contracts, orchestration, and cache policy under
   `core/mt/`, concrete transports under `core/mt/providers/`, and Qt presentation/scheduling in a
   focused `gui/mt_*` adapter rather than `main_window.py`.
2. Implement two provider classes without sharing transport-specific policy:
   - conventional non-LLM MT through a provider-neutral adapter contract and more than one
     documented provider path; Google may be one adapter, but cannot define or be the sole path;
   - context-aware local LLM generation through separate Ollama and llama.cpp-compatible HTTP
     adapters. TranslationZed-Py connects to user-managed runtimes and never installs, starts, or
     downloads runtimes or models.
3. Send conventional providers only the current source, locale direction, and options their shared
   contract can represent. Build deterministic configurable context for local LLMs with initial
   limits of two neighboring rows per side, nearby comments, three top TM matches, and 6,000
   characters. Always retain the current source and protected-token instruction when truncating.
4. Generation is manual in v1. A valid bounded project-cache entry may be shown immediately;
   Regenerate bypasses and replaces it. Automatic background generation is deferred.
5. Key cache entries by provider, adapter version, endpoint/model or engine configuration, locales,
   file/entry, source hash, prompt version when applicable, and context hash.
6. Never auto-apply. Applying uses normal undoable editing, marks `For review`, and reaches project
   TM only through the existing edit/save update path.

### TM-tab presentation and failures

- Render one highlighted machine-translation card, labeled by provider, separately from TM groups
  and ranking. Provider errors or placeholders are not `TMMatch` objects and cannot affect scoring,
  grouping, or diagnostics.
- Suppress stale responses by request identity and row/context key. Cancel or ignore in-flight work
  on file/project switch and shutdown.
- Show authentication/quota, unsupported locale, offline, model-not-found, timeout,
  malformed-response, and context-limit failures without clearing a still-valid cached proposal.

### Verification

- Use fake transports for the provider-neutral conventional contract, each shipped conventional
  adapter, Ollama, and llama.cpp-compatible servers. Cover cache hit/miss, regenerate,
  local-context truncation, authentication, timeouts, malformed output, stale completion,
  cancellation, apply, undo, review marking, and bounded cache eviction. Benchmark
  request-building/cache paths, not external service or model latency.

## 9. Slice 7 — Coherence And Direct Final Release

1. Audit only code touched by v1 slices. Remove proven duplication, keep GUI/core boundaries, and
   avoid line-count-driven moves or speculative abstractions.
2. Review the risk register for touched high-risk modules and update closure evidence only where the
   risk materially changed.
3. Run equivalence and benchmarks for parser/save/search/TM plus new Git/QA/MT workloads. Reproduce
   failures before changing implementations or baselines.
4. Freeze scope; update canonical technical/UX/architecture/testing docs, README, version metadata,
   changelog, and manual scenario contracts to implemented truth.
5. Run focused tests, `make gate-ci-pr`, strict benchmark comparison, heavy advisory review, fresh
   interactive evidence, and `make gate-release TAG=v1.0.0` on one clean commit.
6. Fast-forward `main` to that exact `dev` commit when possible. If integration creates a different
   commit, rerun the release gate. Tag `v1.0.0` directly and verify Linux/macOS/Windows packages,
   smoke runs, archives, and draft release.

## 10. Explicitly Deferred

- User-defined QA rule schemas.
- Git fetch/pull, PR creation, Git credential handling, updater integration, and remote forum
  inspection.
- Theme expansion and automatic background machine translation.
- Broad runtime or Make/CI simplification unrelated to a reproduced v1 blocker.
