# TranslationZed-Py — Module Responsibility Map
_Last updated: 2026-07-16_

## 1) Core Domain And Services

| Module | Responsibility |
|---|---|
| `core.model` | Core entry/status/value models and invariants. |
| `core.translation_format` | Supported translation extensions and format-distinct cache-path identity. |
| `core.translation_json` | Strict flat B42 JSON parsing plus atomic existing-value and missing-member writes. |
| `core.parser` / `core.parse_utils` / `core.lazy_entries` | Format dispatch plus legacy locale parsing, span tracking, and shared lazy value handling. |
| `core.tzp_comment_policy` | Namespaced `TZP:` program-comment parsing/formatting/write-plan contracts. |
| `core.saver` / `core.atomic_io` | Byte-preserving save + atomic replace/write safety, with optional namespaced `TZP:` status-comment write-back. |
| `core.status_cache` / `core.en_hash_cache` | Draft/status cache and EN baseline hash tracking. |
| `core.en_diff_snapshot` / `core.en_diff_service` / `core.en_insert_plan` | EN diff markers (`NEW/REMOVED/MODIFIED`) and insertion planning. |
| `core.git_sync` / `core.git_sync_service` | Read-only local Git/baseline/blob inspection, committed EN change classification, and immutable per-locale synchronization previews; cache application and UI integration remain. |
| `core.project_scanner` | Locale/project discovery and metadata extraction. |
| `core.locale_creation` | Partial v1 foundation: validated staged locale cloning and metadata rewriting; not a completed workflow contract yet. |
| `core.project_session` | Locale/session/tree planning and startup/switch orchestration policies. |
| `core.session_resume` | Project-scoped workspace snapshot DTO/schema validation and cache-file read/write/delete helpers. |
| `core.runtime_diagnostics` | Bounded rotating-log setup, private-path redaction, log-tail reads, and Qt-free GitHub issue-report formatting. |
| `core.file_workflow` | Open/save persistence sequencing plans and callbacks. |
| `core.save_exit_flow` | Save/exit prompt and multi-file write orchestration policies. |
| `core.conflict_service` | Conflict detection/resolution planning and persist decisions. |
| `core.search` / `core.search_replace_service` | Search/replace matching and orchestration plans. |
| `core.qa_rules` / `core.qa_service` | QA primitives, findings generation, panel/navigation planning. |
| `core.languagetool` | LT endpoint policy, level semantics, picky fallback behavior. |
| `core.source_reference_service` | Source-locale switching and deterministic target/reference path resolution. |
| `core.preferences` / `core.preferences_service` | Settings IO normalization, defaults, and persist payloads. |
| `core.app_config` | Static app config parsing (`config/app.toml`). |
| `core.tm_store` / `core.tm_query` / `core.tm_query_engine` / `core.tm_query_policy` / `core.tm_query_scoring` / `core.tm_query_contracts` / `core.tm_query_text` / `core.tm_store_support` / `core.tmx_io` | TM storage, query/ranking internals, deterministic tie-break helpers, and TMX import/export mechanics. |
| `core.tm_import_sync` / `core.tm_preferences` / `core.tm_rebuild` / `core.tm_workflow_service` | TM import lifecycle, preference actions, rebuild and GUI-facing plans. |
| `core.render_workflow_service` | Render-heavy policy decisions for GUI performance paths. |
| `core.encoding_diagnostics` | Read-only encoding diagnostics and reporting utilities. |
| `core.architecture_guard` | Architecture constraints (imports/line budgets). |

## 2) GUI Layer

| Module | Responsibility |
|---|---|
| `gui.main_window` | Qt adapter/orchestrator for menus, widgets, and service delegation. |
| `gui.main_window_panel_helpers` | Sidebar/TM/QA/search/progress helper orchestration. |
| `gui.main_window_en_diff_helpers` | GUI wiring for EN-diff badges and insertion prompts. |
| `gui.manual_scenario_runtime` / `gui.manual_scenario_dialog` | Manual UI scenario runtime contract parsing and checklist modal capture flow. |
| `gui.entry_model` / `gui.commands` | Table model, undo/redo command integration, row mapping. |
| `gui.delegates` | Cell rendering/edit delegates (status, key, multiline, visual text). |
| `gui.fs_model` | Project tree model with locale/file nodes. |
| `gui.status_header` / `gui.table_header` | Header interactions (status sort/filter, source header tools). |
| `gui.source_reference_header` / `gui.source_reference_ui` / `gui.source_reference_state` / `gui.source_lookup` | Source-reference UI and local runtime state. |
| `gui.preferences_dialog` | Preferences UI for General/Search/QA/LanguageTool/TM/View with collapsed-by-default Advanced sections in crowded tabs. |
| `gui.dialogs` | Shared dialogs (locale chooser, save selection, conflict/about, etc.). |
| `gui.locale_creation` | Partial v1 locale-creation warning, input dialog, and chooser composition adapter. |
| `gui.languagetool_adapter` | Editor underline spans/hints integration layer. |
| `gui.qa_async` | Async QA run management and callback wiring. |
| `gui.tm_preview` | TM preview helper rendering/parsing. |
| `gui.progress_metrics` / `gui.progress_widgets` | Progress distribution math and strip widgets. |
| `gui.search_scope_ui` | Search/replace scope indicator widgets. |
| `gui.theme` | Theme detection/apply helpers. |
| `gui.perf_trace` | GUI performance instrumentation helpers. |
| `gui.runtime_reliability` | Project `QLockFile` lifecycle, uncaught-Python exception boundary, and copyable issue-report dialog. |
| `gui.app` | Process-wide `QApplication` bootstrap. |

## 3) Ownership Boundary Rules

1. GUI modules must not implement domain policy that belongs in core services.
2. Core modules must remain Qt-free.
3. Workflow decisions should be exposed through DTO/callback contracts, with GUI
   responsible only for rendering and user interaction.
4. Any new module must be added to this map and referenced by canonical spec docs.

## 4) v0.9 Feature Mapping

Detailed v0.9 feature contracts map to modules as follows:
1. QA live checklist: `gui.qa_async`, `gui.main_window_panel_helpers`, `core.qa_service`.
2. TM explainability: `core.tm_query_engine`, `core.tm_query_scoring`, `core.tm_workflow_service`, TM panel adapters.
3. TM workflow UX: `gui.main_window_panel_helpers`, `gui.tm_preview`, `core.tm_workflow_service`.
4. Crash recovery UC-12 + session resume: `core.project_session`, `core.session_resume`,
   `gui.runtime_reliability`, and startup/recovery adapters in `gui.main_window_panel_helpers`.
