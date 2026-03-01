# TranslationZed-Py — Code Architecture
_Last updated: 2026-03-01_

This document is the concrete code-level architecture reference.
It complements:
- `docs/spec/technical.md` (normative contracts)
- `docs/reference/module_map.md` (ownership map)

## 1) Architecture Paradigm (As Implemented)

TranslationZed-Py uses a pragmatic layered architecture:
1. **Qt adapter shell** in `translationzed_py/gui/*` (`MainWindow` and helpers).
2. **Qt-free workflow services** in `translationzed_py/core/*`.
3. **Deterministic persistence and algorithms** (parser/saver/cache/TM/search).

Operational pattern in code:
- GUI translates user actions into service calls.
- Core services return explicit plan/result DTOs.
- GUI applies plans and owns dialogs/widgets.
- Core never imports Qt types.

## 2) Core Data Model And Types

### 2.1 Core entities and value objects

```mermaid
classDiagram
  class Status {
    <<enum>>
    UNTOUCHED
    FOR_REVIEW
    TRANSLATED
    PROOFREAD
  }

  class Entry {
    +str key
    +str value
    +tuple[int,int] span
    +Status status
    +tuple[str,...] comments
  }

  class ParsedFile {
    +Path path
    +Entry[] entries
    +bytes raw_bytes
    +bool dirty
  }

  class VirtualNewRow {
    +str key
    +str source
    +str draft_value
    +bool edited
  }

  class StatusProgress {
    +int untouched
    +int for_review
    +int translated
    +int proofread
    +int total
  }

  ParsedFile "1" *-- "many" Entry
  Entry --> Status
```

### 2.2 EN diff model set

```mermaid
classDiagram
  class ENDiffResult {
    +frozenset[str] new_keys
    +frozenset[str] removed_keys
    +frozenset[str] modified_keys
  }
  class ENInsertItem {
    +str key
    +str value
    +str before_key
    +str after_key
    +tuple[str,...] comment_block
  }
  class ENInsertPlan {
    +ENInsertItem[] items
    +str preview_text
  }
  ENDiffResult --> ENInsertPlan : drives edited NEW insertion
```

## 3) Core Services, DTOs, And Callback Boundaries

### 3.1 Workflow services and plan DTO contracts

```mermaid
classDiagram
  class ProjectSessionService
  class FileWorkflowService
  class ConflictWorkflowService
  class SearchReplaceService
  class TMWorkflowService
  class QAService

  class LocaleSelectionPlan
  class OpenFileResult
  class SaveCurrentRunPlan
  class ConflictResolutionRunPlan
  class SearchRunPlan
  class TMQueryPlan
  class QAPanelPlan

  ProjectSessionService --> LocaleSelectionPlan
  FileWorkflowService --> OpenFileResult
  FileWorkflowService --> SaveCurrentRunPlan
  ConflictWorkflowService --> ConflictResolutionRunPlan
  SearchReplaceService --> SearchRunPlan
  TMWorkflowService --> TMQueryPlan
  QAService --> QAPanelPlan
```

### 3.2 Adapter-facing callback/protocol points

```mermaid
classDiagram
  class OpenFileCallbacks {
    +load_cache(...)
    +read_file(...)
  }
  class SaveCurrentCallbacks {
    +write_file(...)
    +write_cache(...)
  }
  class CacheMigrationScheduleCallbacks {
    +list_paths(...)
    +migrate(...)
  }
  class TMDiagnosticsStore {
    <<Protocol>>
    +record(...)
  }

  class FileWorkflowService
  class ProjectSessionService
  class TMWorkflowService

  FileWorkflowService --> OpenFileCallbacks
  FileWorkflowService --> SaveCurrentCallbacks
  ProjectSessionService --> CacheMigrationScheduleCallbacks
  TMWorkflowService --> TMDiagnosticsStore
```

Dense source reference:
- `docs/diagrams/src/core_service_contracts_dense.puml`

## 4) GUI Controllers And Adapters

```mermaid
flowchart LR
  MW[gui.main_window.MainWindow]
  MPH[gui.main_window_panel_helpers]
  MEDH[gui.main_window_en_diff_helpers]
  MODEL[gui.entry_model.TranslationModel]
  FS[gui.fs_model.FsModel]
  DELEG[gui.delegates.*]
  HDR[gui.status_header + gui.table_header]
  PREF[gui.preferences_dialog.PreferencesDialog]
  LTUI[gui.languagetool_adapter]
  QAASYNC[gui.qa_async]

  MW --> MPH
  MW --> MEDH
  MW --> MODEL
  MW --> FS
  MW --> DELEG
  MW --> HDR
  MW --> PREF
  MW --> LTUI
  MW --> QAASYNC
```

Dense source reference:
- `docs/diagrams/src/gui_controller_adapters_dense.puml`

## 5) Data Lifecycle (Parse -> Edit -> Cache -> Save)

```mermaid
sequenceDiagram
  participant UI as MainWindow/TranslationModel
  participant FW as core.file_workflow.FileWorkflowService
  participant P as core.parser
  participant SC as core.status_cache
  participant S as core.saver
  participant SNAP as core.en_diff_snapshot

  UI->>FW: prepare_open_file(path)
  FW->>P: parse(path, encoding)
  P-->>FW: ParsedFile(entries, raw_bytes)
  FW->>SC: read(cache)
  FW-->>UI: OpenFileResult + cache overlay

  UI->>SC: write draft/status deltas during editing
  UI->>FW: build_save_current_run_plan(...)
  FW->>S: save(parsed_file, changed_entries)
  S-->>FW: write success/failure
  FW->>SC: rewrite status-only cache
  FW->>SNAP: update EN baseline snapshot for saved file
```

## 6) EN Diff + NEW Insertion Orchestration

```mermaid
sequenceDiagram
  participant UI as gui.main_window_en_diff_helpers
  participant DIFF as core.en_diff_service
  participant SNAP as core.en_diff_snapshot
  participant INS as core.en_insert_plan
  participant SAV as core.saver

  UI->>SNAP: load snapshot
  UI->>DIFF: classify_file(en_text, locale_text, snapshot)
  DIFF-->>UI: ENDiffResult(NEW/REMOVED/MODIFIED)
  UI->>INS: build_insert_plan(edited_new_rows)
  INS-->>UI: ENInsertPlan + preview text
  UI->>SAV: save with Apply/Skip/Edit/Cancel decision
  UI->>SNAP: persist new snapshot after successful save
```

## 7) QA + LanguageTool Integration Sequence

```mermaid
sequenceDiagram
  participant UI as MainWindow QA/T editor
  participant QAASYNC as gui.qa_async
  participant QA as core.qa_service.QAService
  participant LTAD as gui.languagetool_adapter
  participant LT as core.languagetool

  UI->>QAASYNC: start_scan(current file)
  QAASYNC->>QA: scan_qa_rows(...)
  QA-->>QAASYNC: QAFinding[]/QAPanelPlan
  QAASYNC-->>UI: render findings list

  UI->>LTAD: schedule_editor_check(debounce)
  LTAD->>LT: check_text(level=default|picky)
  LT-->>LTAD: LanguageToolCheckResult
  LTAD-->>UI: underline spans + hint window actions
```

## 8) TM Orchestration + Ranking Pipeline

- Module review status: `translationzed_py/core/tm_store.py` closed in A15-TM-RF1
  (`docs/reference/review_queue.json`, `status=CLOSED`, `closed_at=2026-03-01`).

```mermaid
flowchart LR
  UI[TM panel in main_window_panel_helpers]
  WF[core.tm_workflow_service.TMWorkflowService]
  STORE[core.tm_store.TMStore]
  ENGINE[core.tm_query_engine]
  POLICY[core.tm_query_policy]
  SCORING[core.tm_query_scoring]
  CONTRACTS[core.tm_query_contracts]
  VIEW[TMSuggestionsView]

  UI --> WF
  WF --> STORE
  STORE --> ENGINE
  ENGINE --> POLICY
  ENGINE --> SCORING
  ENGINE --> CONTRACTS
  ENGINE --> STORE
  STORE --> WF
  WF --> VIEW
  VIEW --> UI
```

### 8.1 TM Long-Variant Detection Pipeline

```mermaid
flowchart TB
  UI_REQ[TM panel refresh] --> WF_REQ[TMWorkflowService.build_query_request]
  WF_REQ --> STORE_Q[TMStore.query]
  STORE_Q --> QUERY_CONN[TMStore._query_conn]
  QUERY_CONN --> ENGINE[tm_query_engine.query_conn]
  ENGINE --> NORMALIZE[tm_query_policy.normalize_for_match]
  ENGINE --> FUZZY[tm_query_engine.fuzzy_candidates]
  FUZZY --> TOKENS[_query_tokens_cached]

  FUZZY --> BAND[tm_query_policy.compute_candidate_length_band]
  BAND --> BASE_BAND[Lmax_base checkpoint]
  BASE_BAND --> OVER_GUARD[tm_query_policy.allow_oversized_candidate]
  OVER_GUARD --> OVERLAP[_soft_token_overlap]
  OVER_GUARD --> PHRASE[_contains_composed_phrase_cached]
  OVER_GUARD --> RATIO[SequenceMatcher ratio]

  OVERLAP --> SCORE[tm_query_scoring.score_candidate]
  PHRASE --> SCORE
  RATIO --> SCORE
  SCORE --> SORT[tm_query_scoring.sort_scored_candidates]

  SORT --> WF_VIEW[TMWorkflowService.accept_query_result]
  WF_VIEW --> UI_ROWS[TMSuggestionsView rows]
```

## 9) Dependency Direction Contract

```mermaid
flowchart TB
  subgraph GUI[GUI adapters]
    G1[gui.main_window]
    G2[gui.* helpers/models/delegates]
  end
  subgraph CORE[Core workflows + domain]
    C1[core.* services]
    C2[core.model/parser/saver/search/tm]
  end
  subgraph IO[IO backends]
    I1[Filesystem]
    I2[SQLite]
    I3[.tzp/cache]
  end

  G1 --> C1
  G2 --> C1
  C1 --> C2
  C2 --> I1
  C2 --> I2
  C2 --> I3

  X[Forbidden: core -> gui imports]:::forbidden
  C1 -. forbidden .-> G1

  classDef forbidden fill:#7a1f1f,stroke:#ff8080,color:#ffffff;
```

## 10) Programming Model Notes For Contributors

1. Keep business decisions in core service modules, not Qt slots/widgets.
2. Add DTO-first APIs (dataclasses/protocols) for cross-layer boundaries.
3. Keep parser/saver/search/TM changes deterministic and benchmarked.
4. If adding GUI behavior, wire through helper adapters before growing `main_window.py`.
5. Update this document and `docs/reference/module_map.md` when adding or moving ownership.

## 11) Flagged Modules (Document-or-Flag)

Active deep-review entries (see `docs/reference/review_queue.json`):

- FLAGGED_MODULE: translationzed_py/core/preferences.py
  - current behavior: env parsing + normalization + migration orchestration in one module.
  - known limits: high branch density in `_parse_env` reduces readability/change safety.
  - risk notes: intertwined legacy + current key paths can hide regressions.
  - refactor target: split parser/normalizer/migration helpers.
  - tests needed: `tests/test_preferences.py`, `tests/test_preferences_edge_paths.py`,
    `tests/test_preferences_service.py`.

- FLAGGED_MODULE: translationzed_py/core/search_replace_service.py
  - current behavior: search planning, caching policy, replace orchestration in one module.
  - known limits: high branching and wide responsibility surface.
  - risk notes: policy and performance changes are tightly coupled.
  - refactor target: isolate planning/caching/apply helpers.
  - tests needed: `tests/test_search_replace_service.py`,
    `tests/test_search_wave2_equivalence.py`, `tests/test_search_perf_contract.py`.

When a module is flagged in `docs/reference/review_queue.json`, add an explicit marker:

`FLAGGED_MODULE: translationzed_py/<path>.py`

and keep the section factual (current behavior, limits, risk, refactor target, tests).
