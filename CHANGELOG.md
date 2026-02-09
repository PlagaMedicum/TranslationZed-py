# Changelog

All notable changes to this project will be documented in this file.

## [0.5.0] - 2026-02-09

### Added
- **Translation Memory is now usable in daily work**:
  - You can get TM suggestions from both project files and imported TMX files.
  - You can import and export TMX for a source + target locale pair.
  - Imported TMs can be managed in Preferences -> TM (enable/disable, remove, resolve mapping, rebuild, diagnostics).
  - Diagnostics are shown in a copyable report to make troubleshooting easier.
- **Fuzzy matching is broader and more practical**:
  - Similar strings are found with better token/prefix/affix matching.
  - Minimum score is adjustable from `5` to `100` (default `50`).
  - Ranking behavior is now validated by a stable regression corpus.
- **Search workflow is cleaner**:
  - Search runs on explicit actions (Enter / Next / Prev), not on every keystroke.
  - A compact Search side list allows quick jump to found rows.
  - Added case-sensitive toggle in the toolbar.

### Changed
- Local app data is now consistently stored under one folder: `.tzp/`
  (`.tzp/config`, `.tzp/cache`, `.tzp/tms`).
- Older config/import paths are migrated automatically to the new structure.
- Large files now feel smoother to open and scroll due to rendering and row-size optimizations.
- TM controls were decluttered:
  - full management in Preferences -> TM,
  - quick Rebuild button remains in TM sidebar.

### Fixed
- Locale loading is safer:
  - BOM-less UTF-16 fallback is used only when charset is declared in `language.txt`.
  - `language.txt` is mandatory and treated as read-only metadata.
- Conflict behavior is now consistent:
  - keep cached value -> keep cached status,
  - take source/original conflicting value -> set status to `For review`.
- Fixed multiple TM, tooltip, and runtime stability regressions from recent iterations.

### Docs & Tests
- Documentation is more structured and synchronized across spec, UX, and implementation plan.
- Added focused tests for TM diagnostics output and TM ranking recall behavior.
- Release process now includes stronger preflight checks (quality gates + tag/version consistency).

## [0.1.0] - 2026-01-30

### Added
- Initial GUI with file tree, translation table, and status tracking.
- Lossless parser/saver with per-file cache for draft values and statuses.
- Regex search/replace (current file) and multi-file search navigation.
- String editor panel (Source read-only, Translation editable).

### Changed
- Packaging support (PyInstaller) and CI for multi-OS lint/typecheck/tests.

### Known limitations
- No installers yet (folder bundles only).
- No support for dark/light theme mode.
