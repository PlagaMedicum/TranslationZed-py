# TranslationZed-Py — Code Architecture
_Last updated: 2026-03-05_

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

### 3.3 Workflow Internals (Code-Level UML)

#### 3.3.1 `project_session` internals

```mermaid
classDiagram
  class ProjectSessionService {
    +collect_draft_files(...)
    +find_last_opened_file(...)
    +collect_orphan_cache_paths(...)
    +build_locale_selection_plan(...)
    +build_locale_switch_plan(...)
    +build_locale_reset_plan()
    +apply_locale_reset_plan(...)
    +build_post_locale_startup_plan(...)
    +run_post_locale_startup_tasks(...)
    +build_tree_rebuild_plan(...)
    +execute_cache_migration_schedule(...)
    +execute_cache_migration_batch(...)
  }

  class LocaleSelectionPlan
  class LocaleSwitchPlan
  class LocaleResetPlan
  class PostLocaleStartupPlan
  class TreeRebuildPlan
  class CacheMigrationSchedulePlan
  class CacheMigrationBatchPlan
  class CacheMigrationScheduleCallbacks
  class CacheMigrationBatchCallbacks
  class CacheMigrationScheduleExecution
  class CacheMigrationBatchExecution

  ProjectSessionService --> LocaleSelectionPlan
  ProjectSessionService --> LocaleSwitchPlan
  ProjectSessionService --> LocaleResetPlan
  ProjectSessionService --> PostLocaleStartupPlan
  ProjectSessionService --> TreeRebuildPlan
  ProjectSessionService --> CacheMigrationSchedulePlan
  ProjectSessionService --> CacheMigrationBatchPlan
  ProjectSessionService --> CacheMigrationScheduleCallbacks
  ProjectSessionService --> CacheMigrationBatchCallbacks
  ProjectSessionService --> CacheMigrationScheduleExecution
  ProjectSessionService --> CacheMigrationBatchExecution
```

```mermaid
sequenceDiagram
  participant GUI as main_window
  participant PS as project_session
  GUI->>PS: resolve_requested_locales(...)
  GUI->>PS: build_locale_switch_plan(...)
  GUI->>PS: build_locale_reset_plan()
  GUI->>PS: apply_locale_reset_plan(...callbacks...)
  GUI->>PS: build_post_locale_startup_plan(...)
  GUI->>PS: run_post_locale_startup_tasks(...)
  GUI->>PS: build_tree_rebuild_plan(...)
```

#### 3.3.2 `file_workflow` internals

```mermaid
classDiagram
  class FileWorkflowService {
    +prepare_open_file(...)
    +apply_cache_overlay(...)
    +apply_cache_for_write(...)
    +build_save_current_run_plan(...)
    +persist_current_save(...)
    +write_from_cache(...)
  }

  class OpenFileCallbacks
  class OpenFileResult
  class CacheOverlayResult
  class CacheWriteOverlay
  class SaveCurrentRunPlan
  class SaveCurrentCallbacks
  class SaveCurrentResult
  class SaveFromCacheCallbacks
  class SaveFromCacheResult
  class SaveFromCacheParseError

  FileWorkflowService --> OpenFileCallbacks
  FileWorkflowService --> OpenFileResult
  FileWorkflowService --> CacheOverlayResult
  FileWorkflowService --> CacheWriteOverlay
  FileWorkflowService --> SaveCurrentRunPlan
  FileWorkflowService --> SaveCurrentCallbacks
  FileWorkflowService --> SaveCurrentResult
  FileWorkflowService --> SaveFromCacheCallbacks
  FileWorkflowService --> SaveFromCacheResult
  FileWorkflowService --> SaveFromCacheParseError
```

```mermaid
sequenceDiagram
  participant GUI as main_window
  participant FW as file_workflow
  participant PARSE as parser
  participant CACHE as status_cache
  participant SAVE as saver

  GUI->>FW: prepare_open_file(path, encoding, callbacks, hash_for_entry)
  FW->>PARSE: parse_eager/parse_lazy
  FW->>CACHE: read_cache + overlay
  GUI->>FW: build_save_current_run_plan(...)
  GUI->>FW: persist_current_save(..., callbacks)
  FW->>SAVE: save_file(...)
  FW->>CACHE: write_cache(...)
```

#### 3.3.3 `search_replace_service` internals

```mermaid
classDiagram
  class SearchReplaceService {
    +scope_files(...)
    +build_search_run_plan(...)
    +find_match_in_rows(...)
    +search_across_files(...)
    +build_replace_request(...)
    +build_replace_all_run_plan(...)
    +apply_replace_all(...)
  }

  class SearchRunPlan
  class SearchPanelPlan
  class SearchPanelItem
  class SearchRowsCacheKey
  class SearchRowsCacheStamp
  class SearchRowsCacheLookupPlan
  class SearchRowsCacheStorePlan
  class SearchRowsSourcePlan
  class SearchRowsBuildResult
  class SearchMatchOpenPlan
  class SearchMatchApplyPlan
  class ReplaceRequest
  class ReplaceAllPlan
  class ReplaceAllRunPlan
  class ReplaceAllFileCountCallbacks
  class ReplaceAllFileApplyCallbacks
  class ReplaceAllRowsCallbacks
  class ReplaceCurrentRowCallbacks
  class ReplaceAllFileApplyResult
  class ReplaceAllRowsApplyResult
  class ReplaceRequestError
  class ReplaceAllFileParseError

  SearchReplaceService --> SearchRunPlan
  SearchReplaceService --> SearchPanelPlan
  SearchReplaceService --> SearchPanelItem
  SearchReplaceService --> SearchRowsCacheKey
  SearchReplaceService --> SearchRowsCacheStamp
  SearchReplaceService --> SearchRowsCacheLookupPlan
  SearchReplaceService --> SearchRowsCacheStorePlan
  SearchReplaceService --> SearchRowsSourcePlan
  SearchReplaceService --> SearchRowsBuildResult
  SearchReplaceService --> SearchMatchOpenPlan
  SearchReplaceService --> SearchMatchApplyPlan
  SearchReplaceService --> ReplaceRequest
  SearchReplaceService --> ReplaceAllPlan
  SearchReplaceService --> ReplaceAllRunPlan
  SearchReplaceService --> ReplaceAllFileCountCallbacks
  SearchReplaceService --> ReplaceAllFileApplyCallbacks
  SearchReplaceService --> ReplaceAllRowsCallbacks
  SearchReplaceService --> ReplaceCurrentRowCallbacks
  SearchReplaceService --> ReplaceAllFileApplyResult
  SearchReplaceService --> ReplaceAllRowsApplyResult
  SearchReplaceService --> ReplaceRequestError
  SearchReplaceService --> ReplaceAllFileParseError
```

```mermaid
sequenceDiagram
  participant GUI as main_window
  participant SR as search_replace_service
  participant SEARCH as core.search

  GUI->>SR: scope_files(...)
  GUI->>SR: build_search_run_plan(...)
  GUI->>SEARCH: prepare_search_plan(...)
  GUI->>SR: build_search_rows(...)
  GUI->>SR: find_match_in_rows(..., prepared_plan)
  GUI->>SR: search_across_files(...)
  GUI->>SR: build_replace_request(...)
  GUI->>SR: build_replace_all_run_plan(...)
  GUI->>SR: apply_replace_all(...)
```

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

## 7) QA + LanguageTool Integration Sequence (Current v0.8.0)

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

### 7.1 v0.9 target: QA live checklist call chain

```mermaid
sequenceDiagram
  participant UI as MainWindow QA panel
  participant ASYNC as gui.qa_async
  participant QA as core.qa_service
  participant LT as core.languagetool

  UI->>ASYNC: run_qa_scan(file, rules_plan)
  ASYNC-->>UI: QARuleProgressRecord(state=queued) x N
  ASYNC-->>UI: QARuleProgressRecord(state=running, rule=trailing)
  ASYNC->>QA: run trailing/newline/token/same-source rules
  QA-->>ASYNC: findings + per-rule completion
  ASYNC-->>UI: per-rule state updates (done/skipped/failed)
  ASYNC->>LT: optional LT stage (non-blocking)
  LT-->>ASYNC: LT findings / warning note
  ASYNC-->>UI: final snapshot + completion ratio
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

### 8.2 v0.9 target: TM explainability call chain

```mermaid
sequenceDiagram
  participant UI as TM panel
  participant WF as TMWorkflowService
  participant STORE as TMStore
  participant ENG as tm_query_engine
  participant SCORE as tm_query_scoring

  UI->>WF: request suggestions(query, min_score)
  WF->>STORE: query(...)
  STORE->>ENG: query_conn(...)
  ENG->>SCORE: score_candidate(...)
  SCORE-->>ENG: score + tie-break + explanation factors
  ENG-->>STORE: ordered matches + explainability payload
  STORE-->>WF: query result
  WF-->>UI: rows + why-matched metadata
```

## 9) v0.9 target: Startup crash recovery call chain

```mermaid
sequenceDiagram
  participant APP as app startup
  participant MW as MainWindow
  participant PS as project_session
  participant CR as crash-recovery service
  participant DLG as recovery dialog

  APP->>PS: build startup/open plan
  PS->>CR: detect recovery candidates
  CR-->>MW: CrashRecoveryReport | none
  MW->>DLG: show Restore/Discard/Cancel + plaintext details
  DLG-->>MW: decision
  MW->>CR: apply decision
  MW->>PS: continue open flow or abort safely
```
## 10) Dependency Direction Contract

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

## 11) Programming Model Notes For Contributors

1. Keep business decisions in core service modules, not Qt slots/widgets.
2. Add DTO-first APIs (dataclasses/protocols) for cross-layer boundaries.
3. Keep parser/saver/search/TM changes deterministic and benchmarked.
4. If adding GUI behavior, wire through helper adapters before growing `main_window.py`.
5. Update this document and `docs/reference/module_map.md` when adding or moving ownership.

## 12) Document-or-Flag Status

Current queue state:
1. Active queue entries:
   - `FLAGGED_MODULE: translationzed_py/core/project_session.py`
   - status: `IN_REFACTOR` (`A26`, crash-recovery decision application + safety guards)
   - `FLAGGED_MODULE: translationzed_py/core/tm_query_engine.py`
   - status: `IN_REFACTOR` (`A21`, TM explainability determinism guards)
   - `FLAGGED_MODULE: translationzed_py/core/saver.py`
   - status: `IN_REFACTOR` (`A30-TZP-2`, optional `TZP:` write-back integration in save path)
2. Previous P1 entries (`preferences.py`, `search_replace_service.py`,
   `tm_store.py`) are closed and retained as historical evidence.

Rule when new risk is detected:
1. Add `FLAGGED_MODULE: translationzed_py/<path>.py` in this document.
2. Add queue entry in `docs/reference/review_queue.json` with closure criteria.
3. Keep only factual internals for flagged modules until closure.
