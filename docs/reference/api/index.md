# API Reference (Core)
_Updated: 2026-06-23_

This section is generated from source docstrings using `mkdocstrings + griffe`, with
curated architecture context added for human and LLM readability.

## 1) Reading Contract

1. Each page starts with intent, boundaries, and call-flow before symbol dumps.
2. `mkdocstrings` blocks are authoritative symbol inventories.
3. For modules in the active risk register, preserve the listed constraints and focused tests.

## 2) Page Map

1. `docs/reference/api/core_workflows.md`
   1. orchestration services and request/result planning boundaries.
2. `docs/reference/api/core_data_io.md`
   1. parser/saver/cache/TM and deterministic storage contracts.
3. `docs/reference/api/core_preferences.md`
   1. settings persistence, normalization, and runtime preference application.

## 3) Stability Notes

1. Public runtime behavior contracts are normative in `docs/spec/technical.md`.
2. API docs describe implementation shape, not product requirements.
3. Active risk and verification guidance lives in `docs/reference/risk_register.md`.
