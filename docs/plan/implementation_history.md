# Decision And Lessons Ledger

_Updated: 2026-06-23_

This is durable, non-normative history. Current behavior belongs in the technical, UX, domain, and
architecture documents. Current work belongs in `implementation_active.md`. Detailed milestone and
packet execution logs remain available through git history.

## Architecture

### Qt-free workflow policy

GUI modules own widgets, rendering, signals, dialogs, and focus state. Core modules own workflow
decisions and remain Qt-free. This boundary made complex save, conflict, search, QA, TM, and
startup behavior testable without driving widgets.

Lesson: extracting policy is useful when it creates a stable non-Qt decision boundary. Splitting a
module only to satisfy file size or diagram shape is not sufficient.

### Adapter-first main window

`MainWindow` remains the top-level Qt adapter. Its size is an active risk, but moving policy back
into GUI helpers would make the architecture worse. Reductions should remove duplication or move
coherent policy into core services while preserving UI ownership in the adapter.

### Explicit persistence plans

Open, save, conflict, cache migration, and exit behavior use explicit plans/results and callbacks.
This keeps filesystem mutation visible and allows no-write paths to be tested directly.

## Data Safety And Compatibility

### Byte-preserving translation edits

The parser and saver preserve comments, whitespace, ordering, concatenation structure, line
endings, and other non-literal bytes. Optimizations are acceptable only when spans, decoded values,
and saved structure remain equivalent.

### Locale-declared encoding

Locale `language.txt` metadata is authoritative for translation-file encoding. UTF-8, single-byte
encodings, and UTF-16—including supported no-BOM inputs—must round-trip without implicit
transcoding.

### Cache-first draft safety

Editing persists drafts to project-local cache. Opening or switching context must not write original
translation files. Writing originals requires an explicit user decision and atomic replacement.

### Recovery and session resume

Crash recovery uses explicit Restore, Discard, and Cancel decisions. Session snapshots are
project-scoped, versioned cache data. A valid snapshot is applied before last-opened-file fallback;
invalid snapshots are ignored safely.

## Product Behavior

### Source reference semantics

The selected reference locale is shown when the matching file exists. If it does not exist, the
Source column remains empty. Older fallback-chain and per-locale preset experiments are not current
product behavior.

### Namespaced status comments

Program-managed `TZP:` status comments are opt-in. The default saver path remains byte-preserving,
and non-`TZP:` user comments are immutable. The old editable status-comment prefix is not a
user-facing preference.

### Search and replace safety

Search and replacement scopes are explicit. Replace-all uses a deterministic impact preview and
requires confirmation before applying changes. Cancellation must leave all target files unchanged.

### QA and LanguageTool

QA rule order and progress are deterministic. LanguageTool is optional and non-blocking; timeout,
offline, and unsupported-mode failures do not invalidate other QA results. Stale asynchronous
results are discarded.

### Translation memory

TM retrieval, scoring, caps, and tie-breaks are deterministic. Explainability reports the existing
decision path and must not alter ranking. Candidate pools and caches remain bounded to protect
interactive latency and memory.

## Verification

### Invariants before coverage volume

The most valuable tests protect no-write-on-open, byte-exact round trips, encoding fidelity,
deterministic ordering, atomic writes, and bounded behavior. Coverage floors support these tests but
do not replace them.

### Manual scenarios

Automated GUI tests do not establish every operator-visible workflow. Structured manual scenarios
cover real app actions, finish conditions, and on-disk inspection where required. Interactive
pass/fail judgment and release evidence acceptance remain human-owned.

### Performance work

Measure before optimizing. Parser, search, and TM optimizations require semantic equivalence tests
and robust repeated measurements. A faster path that changes ordering, spans, or accepted inputs is
a behavior change, not an optimization.

### Release metadata

Release checks align the tag, `pyproject.toml`, `translationzed_py/version.py`, and changelog.
Manual evidence and benchmark results are evidence, not files to rewrite until a gate becomes green.

## Documentation And LLM Workflow

### Task-oriented context

`quick_context`, `module_map`, and `test_surface` exist to avoid broad repository scans. UX pages
describe observable behavior; technical and architecture pages describe system contracts; focused
domain pages preserve formulas and proof obligations.

### Canonical ownership without synchronization cascades

One document owns each kind of fact. Summaries link to owners and are updated only when inaccurate.
Exact prose, repeated command inventories, and completed packet narratives are not useful
cross-document contracts.

### Generated context is disposable

The full symbol index became large, frequently stale, and mostly duplicated source. Targeted
on-demand generation provides the useful navigation function without committing hundreds of
kilobytes or forcing unrelated updates.

### Risk information stays active

The risk register contains only modules that currently require special care and the tests that
protect them. Closed entries are removed after their durable lesson is encoded in tests, code,
architecture, or this ledger.

## Historical Detail

Use git history when exact packet chronology, closure evidence, or superseded designs are needed:

```bash
git log -- docs/plan/implementation_history.md
git show <commit>:docs/plan/implementation_history.md
```
