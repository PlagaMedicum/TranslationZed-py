# TranslationZed-Py — Architecture Diagrams
_Last updated: 2026-03-04_

This page is the high-level diagram index.
For code-level dependency and extension rules, see `docs/architecture/code_architecture.md`.

Mermaid in this page is the maintained source. Canonical docs render one primary diagram only; do
not add unreferenced alternate source or static copies.

## 1) System Context

```mermaid
flowchart LR
  U[Translator / Proofreader] --> GUI[Qt GUI]
  GUI --> CORE[Core Services]
  CORE --> FS[(Locale Files)]
  CORE --> CACHE[(.tzp/cache)]
  CORE --> TM[(TM SQLite Store)]
```

## 2) Layered Architecture

```mermaid
flowchart TB
  GUI[GUI Layer\nmain_window + models/delegates] --> APP[Workflow Services\nQt-free orchestration]
  APP --> CORE[Domain/Core\nparser/saver/search/qa/tm]
  CORE --> INFRA[Infrastructure IO\nfilesystem/cache/sqlite]
```

## 3) Core Services Interaction Graph

```mermaid
graph LR
  PS[project_session] --> FW[file_workflow]
  FW --> SX[save_exit_flow]
  FW --> CS[conflict_service]
  FW --> SC[status_cache]
  SR[search_replace_service] --> QA[qa_service]
  TMW[tm_workflow_service] --> TMS[tm_store]
  TMW --> TMI[tm_import_sync]
```

## 4) GUI Adapters/Controllers Interaction Graph

```mermaid
graph LR
  MW[main_window] --> PM[panel_helpers]
  MW --> ED[entry_model]
  MW --> SH[status_header]
  MW --> LT[languagetool_adapter]
  MW --> PR[preferences_dialog]
```

## 5) Save Flow Sequence

```mermaid
sequenceDiagram
  participant U as User
  participant GUI as main_window
  participant C as status_cache
  participant S as saver
  U->>GUI: Edit translation
  GUI->>C: persist draft cache
  U->>GUI: Save
  GUI->>S: write selected files
  S-->>GUI: success/failure
  GUI->>C: rewrite status-only cache
```

## 6) Open / Parse / Conflict Sequence

```mermaid
sequenceDiagram
  participant U as User
  participant GUI as main_window
  participant F as file_workflow
  participant P as parser
  participant X as conflict_service
  U->>GUI: Open file
  GUI->>F: build open plan
  F->>P: parse locale file
  F->>X: evaluate cache/original mismatch
  X-->>GUI: prompt plan or clean load
```

## 7) EN Diff + NEW Insertion Sequence

```mermaid
sequenceDiagram
  participant GUI as main_window
  participant D as en_diff_service
  participant I as en_insert_plan
  GUI->>D: classify NEW/REMOVED/MODIFIED
  D-->>GUI: row marker payload
  GUI->>I: build insertion preview for edited NEW rows
  I-->>GUI: Apply/Skip/Edit/Cancel preview
```

## 8) Status Triage State Machine

```mermaid
stateDiagram-v2
  [*] --> Untouched
  Untouched --> ForReview: QA / manual mark
  ForReview --> Translated: mark translated
  Translated --> Proofread: mark proofread
  Proofread --> ForReview: re-open for review
```

## 9) QA + LanguageTool Pipeline

```mermaid
flowchart LR
  A[Run QA] --> Q[qa_service checks]
  Q --> R[QA findings list]
  T[Inline LT check] --> L[languagetool adapter]
  L --> R
```

## 10) TM Ranking Query Activity

```mermaid
flowchart TB
  Q[Source text query] --> N[Normalize + partial wrapper cleanup]
  N --> E[Exact retrieval]
  E --> F[Fuzzy candidate pools]
  F --> B[Adaptive band by Lq,k]
  B --> OG[Oversized candidate guard stage]
  OG --> G[Relevance gates]
  G --> S[Score + tie-break]
  S --> O[Ordered suggestions]
```

### 10.1 TM Long-Variant Detection Activity

```mermaid
flowchart LR
  LQ[Query length and token count] --> BASE[Base length band]
  BASE --> TRIG{Long multi-token}
  TRIG -- no --> BAND0[Use base band]
  TRIG -- yes --> BAND1[Use adaptive band]
  BAND0 --> PICK[Candidate selected]
  BAND1 --> PICK
  PICK --> OVER{Above base upper band}
  OVER -- no --> KEEP[Proceed to scoring]
  OVER -- yes --> RULE{Oversized guard satisfied}
  RULE -- no --> DROP[Reject candidate]
  RULE -- yes --> KEEP
```

## 11) Verification Pipeline

```mermaid
flowchart LR
  D[make gate-dev] --> S[static + architecture + locale checks]
  P[make gate-push] --> T[core + routed + readonly checks]
  C[make gate-ci-pr] --> CI[coverage + docs + security + perf contracts]
  H[make gate-heavy-advisory] --> HE[property + heavy perf + mutation]
  R[make gate-release] --> RE[CI + strict benchmark + heavy + release evidence]
```

## 12) Module Dependency Map

```mermaid
flowchart LR
  subgraph GUI
    MW[main_window]
    EM[entry_model]
    DG[delegates]
  end
  subgraph CORE
    PS[project_session]
    FW[file_workflow]
    SR[search_replace_service]
    TMW[tm_workflow_service]
    QA[qa_service]
  end
  subgraph DATA
    PARSER[parser/saver]
    CACHE[status_cache]
    TMDB[tm_store]
  end
  MW --> PS
  MW --> FW
  MW --> SR
  MW --> TMW
  MW --> QA
  FW --> PARSER
  FW --> CACHE
  TMW --> TMDB
```

## 13) QA Live Checklist Pipeline

```mermaid
flowchart LR
  RUN[Run QA] --> PLAN[Create ordered rule plan]
  PLAN --> TRACE[Emit queued states]
  TRACE --> EXEC[Run rules one by one]
  EXEC --> LT[Optional LT stage]
  LT --> SNAP[Build final progress snapshot]
  SNAP --> UI[Render checklist and summary]
```

## 14) TM Explainability Delivery

```mermaid
flowchart LR
  QUERY[TM query request] --> MATCH[Retrieve and score matches]
  MATCH --> EXPL[Build explainability payload]
  EXPL --> ORDER[Deterministic ordering]
  ORDER --> PANEL[TM list and explanation panel]
```

## 15) Crash Recovery Startup Decision

```mermaid
flowchart LR
  START[Startup open request] --> LOCK{Acquire session.lock}
  LOCK -- live owner --> ABORT[Explain conflict and abort open]
  LOCK -- clean --> DETECT[Detect draft candidates]
  LOCK -- stale replaced --> UNCLEAN[Mark previous session unclean]
  UNCLEAN --> DETECT
  DETECT --> ASK{Unclean signal and draft report}
  ASK -- no --> CONTINUE[Continue normal open flow]
  ASK -- yes --> DIALOG[Show Restore Discard Cancel dialog]
  DIALOG --> APPLY[Apply selected action]
  APPLY --> RESULT[Continue open or abort safely]
```
