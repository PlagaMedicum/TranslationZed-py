# Changelog

All notable changes to this project will be documented in this file.

## [0.9.0] - 2026-07-13

### Added
- QA now shows which checks are waiting, running, finished, skipped, or failed.
- QA now shows a short result summary when a check is finished. You can also limit the number of results when working with large files.
- Translation Memory can now explain why a suggestion matched and how it received its score.
- TM suggestions can be grouped by source or score. You can move between them and apply them with the keyboard.
- Crash recovery now appears after an interrupted session. You can restore your drafts, discard them, or cancel opening the project.
- The app can restore the last open file and your previous workspace when started again.
- Search and Replace controls are now available in the Search sidebar as well as the toolbar.
- Replace All can work on the current file, the current locale, or the whole translation project.
- A preview now shows which files and rows will change before Replace All is applied.
- A new option can save `TZP:` translation status comments inside locale files. This is disabled by default.
- The status bar now shows when selected rows have different translation statuses.
- The status bar now shows the encoding of the current file.

### Changed
- QA progress takes less space and is easier to read.
- Manual QA checks show a result popup. Automatic checks report quietly in the status bar.
- The Source column now shows only the source locale you selected. If that locale has no matching file, the column stays empty instead of showing text from another locale.
- Replace All now asks you to confirm where it should run and review the changes before applying them.
- Translation Memory shows clearer messages when there are no suggestions or when something goes wrong.
- Old or missing preferences are cleaned up automatically.
- Opening files, parsing translations, and searching are faster and more reliable.

### Fixed
- Fixed old QA results appearing after switching files or starting another check.
- Fixed translation statuses changing more than once when automatic QA marking is enabled.
- Fixed startup problems when saved session data is broken or refers to a missing file.
- Fixed incorrect Source column behavior when the selected source locale has no matching file.
- Fixed several Replace All problems related to the selected area and previewed changes.
- Fixed several editor and dialog problems that could appear while opening projects or working with unsaved changes.

## [0.8.0] - 2026-03-04

### Added
- Built-in LanguageTool writing assistance in the editor, including inline issue highlighting and quick-fix suggestions.
- Optional LanguageTool checks in manual QA runs, with row limits to keep QA responsive on large files.
- New EN-diff awareness in the editor with `NEW`, `MODIFIED`, and `REMOVED` markers.
- Save-time insertion flow for edited `NEW` rows, with preview and confirmation before applying changes.
- Status triage tools: status sorting/filtering and priority navigation (`Untouched -> For review -> Translated -> Proofread`).
- Progress HUD in the `Project` panel showing locale and current-file translation/proofread progress.
- Browser-first documentation portal with architecture diagrams, API pages, and stricter docs quality checks.

### Changed
- LanguageTool behavior now matches browser-style picky mode semantics and falls back safely when picky mode is unavailable.
- Translation Memory matching improved for long edited variants and duplicated-segment artifacts, with stronger default recall at standard thresholds.
- Verification flow tightened across local and CI lanes with clearer strict vs advisory behavior.
- Search and QA panel UX streamlined for clearer navigation, lower clutter, and better empty-state guidance.
- Main window responsibilities reduced via helper extractions and architecture guard enforcement.

### Fixed
- Fixed false `REMOVED` floods in EN-diff labeling caused by locale-suffixed EN path resolution.
- Fixed multiple sidebar/table resize and relayout regressions affecting main grid width behavior.
- Fixed cross-platform verification issues (Windows/macOS/Linux shell and path consistency).
- Fixed docs rendering/navigation regressions (local `.html` navigation, math/list rendering checks).
- Fixed LanguageTool edge cases including delayed hint popup for double-click word selection and HTTP resource handling.

## [0.7.0] - 2026-02-16

### Added
- Dark theme support synchronized with system theme;
- More deterministic cross-platform path normalization in diagnostics, prompts, and search labels;
- Better save flow transparency (changed-file prompts and improved write intent visibility).
- Additional TM import formats and stronger TM relevance/ranking coverage;
- Source-reference switch. You can now change source column's locale on the fly;
- QA tab with basic QAs for translations;
- New source-reference core/service helpers with dedicated unit and GUI integration coverage;
- More automated tests and diagnostics stuff;
- Added more indicators to the UI, like characters counter in the bottom-right cormer;
- Additional regression checks for source-mode search/cache behavior and large-file source-reference switch performance.

### Changed
- UI improved and is more responsive and ordered;
- Refactored a lot of code, improved architecture of the project;
- Updated documentation;
- Improved preferences;
- CI/release checks are stricter and include cross-platform gating before final tagging.

### Fixed
- Stale source-cache/search behavior when switching Source reference locale;
- Preference-apply edge cases around fallback policy updates and file-level Source override cleanup;
- Windows-specific path and separator regressions in tests and service outputs;
- TM preview/query robustness and UI edge-case behavior during panel operations.

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
