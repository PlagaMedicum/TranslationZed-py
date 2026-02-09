# Changelog

All notable changes to this project will be documented in this file.

## [0.5.0] - 2026-02-09

### Added
- Translation Memory (TM) subsystem:
  - Project TM SQLite store at `.tzp/config/tm.sqlite`.
  - TMX import/export for source+target locale pairs.
  - Managed imported-TM folder at `.tzp/tms` with sync-on-open behavior.
  - Preferences -> TM operations: import, resolve pending mappings, enable/disable, remove, export, rebuild, diagnostics.
  - Diagnostics report with copyable output and query/import visibility metrics.
- TM ranking contract and coverage:
  - Token/prefix/affix-aware fuzzy matching with EN-adapted stemming.
  - Score threshold range `5..100` (default `50`), origin filters, and deep-query limits for low-threshold recall.
  - Deterministic corpus-based acceptance tests for fuzzy ranking/regression behavior.
- Service-layer extraction for main workflows (Qt-free core orchestration):
  - `ConflictService`, `FileWorkflowService`, `SearchReplaceService`, `PreferencesService`,
    `RenderWorkflowService`, `TMWorkflowService`, `tm_import_sync`, `tm_query`, `tm_preferences`,
    `tm_rebuild`, `save_exit_flow`, `project_session`.
- Search UX improvements:
  - Search executes on explicit actions (Enter/Next/Prev), not on typing.
  - Minimal Search side-panel results list with direct navigation.
  - Case-sensitive toggle in the toolbar.
- Expanded performance and verification tooling:
  - Perf trace categories (`TZP_PERF_TRACE=...`) for hotspot diagnosis.
  - Fixture-backed perf scenarios integrated into `make verify`.

### Changed
- Runtime-local state layout normalized under `.tzp/`:
  - `.tzp/config/settings.env`
  - `.tzp/cache/*`
  - `.tzp/tms/*`
- Legacy config/import paths are auto-migrated to canonical `.tzp` paths.
- Large-file behavior tuned for smoother row sizing/paint and on-demand text preview paths.
- TM command surface decluttered: operational controls are centralized in Preferences -> TM,
  with a compact Rebuild glyph button in TM sidebar.

### Fixed
- UTF-16 BOM-less parsing fallback now depends on valid `language.txt` charset metadata.
- `language.txt` is enforced as mandatory and read-only (malformed/missing locale blocks opening that locale).
- Conflict-resolution status semantics:
  - Keep cache value -> preserve cached status.
  - Take original conflicting value -> force status `For review`.
- Multiple TM/tooltip/runtime regressions in recent iterations (PySide API compatibility and stale UI paths).

### Docs & Tests
- Documentation structure and ownership clarified (`docs/docs_structure.md`).
- Use-case/spec/plan synchronization improved, including TM diagnostics and ranking behavior.
- Added targeted UI tests for TM diagnostics output and extended TM ranking corpus assertions.

## [0.1.0] - 2026-01-30

### Added
- Initial GUI with file tree, translation table, and status tracking.
- Lossless parser/saver with per-file cache for draft values and statuses.
- Regex search/replace (current file) and multi-file search navigation.
- String editor panel (Source read-only, Translation editable).
- About dialog with GPL notice and expandable license.

### Changed
- Packaging support (PyInstaller) and CI for multi-OS lint/typecheck/tests.

### Known limitations
- No installers yet (folder bundles only).
- No support for dark/light theme mode.
