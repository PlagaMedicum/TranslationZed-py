# Changelog

All notable changes to this project will be documented in this file.

## [0.1.0] - Unreleased

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
- Dark mode follows system style only; no custom theme.
