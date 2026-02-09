# Changelog

All notable changes to this project will be documented in this file.

## [0.5.0] - 2026-02-09

### Added
- **Added Translation Memory**:
  - You can get TM suggestions from both project files and imported TMX files.
  - You can import and export TMX for a source + target locale pair.
  - Imported TMs can be managed in Preferences -> TM (enable/disable, remove, resolve mapping, rebuild, diagnostics).
  - Diagnostics are shown in a copyable report to make troubleshooting easier.
  - Minimum score is adjustable from `5` to `100` (default `50`).
  - Ranking behavior is validated by a stable regression corpus.
- **Search workflow is cleaner**:
  - Search runs on explicit actions (Enter / Next / Prev), not on every keystroke.
  - A compact Search side list allows quick jump to found rows.
  - Added case-sensitive toggle in the toolbar.
- **Added syntax and whitespaces+newline chars highlighting options**
- **Added more toggles and preferences**
- **Some other features, that we are accustomed to with all CATs**

### Changed
- Side-bar is now separated between filetree, TM and Search results. Search results tab is currently drafted, but still usable.
- Local app data is now consistently stored under one folder: `.tzp/`
  (`.tzp/config`, `.tzp/cache`, `.tzp/tms`).
- Older config/import paths are migrated automatically to the new structure.
- Large files now feel smoother to open and scroll due to rendering and row-size optimizations.

### Fixed
- Locale loading is safer:
  - BOM-less UTF-16 fallback is used only when charset is declared in `language.txt`.
  - `language.txt` is mandatory and treated as read-only metadata.
- Conflict behavior is now consistent:
  - added cache-original file changes conflict mitigation with merging window.
  - overall, the app is more robust for unexpected conflicts and has a lot of warnings if something is not ok with files.
- Fixed runtime stability regressions from recent iterations.

### Docs & Tests
- Documentation is more structured and synchronized across spec, UX, and implementation plan.
- Added focused tests for TM diagnostics output and TM ranking recall behavior. Overall, there is much more of tests coverage.
- Added perf tests and more capabilities for diagnostics.
- Release process now includes stronger preflight checks (quality gates + tag/version consistency).

## [0.1.0] - 2026-01-30

This is initial release with some basic features to parse and edit PZ translations files. There is functional GUI, search, replace, regex, filetree, editing, different search/replace scopes. Made foundations of documentation and architecture of the project. Prepared the repo, packaging and CIs. Ensured basic testing of the code.
