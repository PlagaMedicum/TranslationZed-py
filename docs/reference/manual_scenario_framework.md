# Manual Scenario Framework

## Purpose

This page is the canonical reference for the reusable manual UI scenario framework.
It defines the scenario schema, runtime artifact model, and release-evidence flow.
The canonical scenario matrix lives in `docs/reference/test_surface.md`.

## Scenario Schema

Registry file:
- `tests/manual_scenarios/scenarios.json`

Required fields:
- `id`
- `title`
- `workflow_family`
- `manual_depth`
- `goal`
- `start_context`
- `fixture_root`
- `focus_files`
- `finish_condition`
- `selected_locales`
- `steps`
- `expected_checks`
- `tracked_repo_files`

Optional fields:
- `env_overrides`
- `prefs_extras`
- `automation_pytest_selectors`
- `operator_hints`
- `inspection_paths`

Field intent:
- `focus_files`: fixture-relative files the operator must touch in the scenario.
- `inspection_paths`: fixture-relative files the operator may need to inspect on disk.
- `tracked_repo_files`: repo-relative files whose sha256 rows gate release-evidence relevance.
- `operator_hints`: short operator-facing guidance for prompts, inspection, or ambiguity handling.

Authoring rules:
- scenarios must use real app actions only
- save/write expectations must be explicit when the scenario depends on them
- when a scenario expects an on-disk save, it must say whether the operator should choose `Write to file` or cache-only save if the UI offers both
- `close file` / `re-open file` wording is banned
- vague wording such as `Open a file` is banned for release-required scenarios
- inspection steps must name concrete `inspection_paths`

## Runtime Surface

Scenario mode is activated by:
- `TZP_MANUAL_SCENARIO_FILE=<payload.json>`
- `TZP_MANUAL_RESULTS_DIR=<output-dir>`
- `TZP_MANUAL_RUN_TOKEN=<token>`

Checklist dialog contract:
- shows `Goal`, `Start context`, `Focus files`, `Finish condition`
- shows optional `Operator hints` and `Inspection paths`
- keeps operator notes in the checklist artifact so successful runs can still record ambiguity or follow-up cleanup
- exposes copy actions for:
  - project root
  - focus paths
  - inspection paths
- `Mark Passed` stays disabled until all steps and expected outcomes are checked

## Artifact Model

Interactive checklist artifacts are written under:
- `artifacts/manual-ui/*.json`

Run artifacts record:
- embedded scenario payload
- copied fixture root
- manual outcome
- optional automation outcome
- tracked file hash rows

Checklist artifacts record:
- checked steps
- checked expected outcomes
- operator notes
- completion timestamp

## Release Evidence

Tracked release-evidence files:
- `tests/manual_scenarios/release_evidence_manifest.json`
- `tests/manual_scenarios/release_evidence/*.json`

Strict rules:
- every scenario in `tests/manual_scenarios/scenarios.json` is required
- evidence must come from interactive passed runs
- `headless` and `auto-only` artifacts are not acceptable release evidence
- if any `tracked_repo_files` hash changes, evidence becomes stale and must be re-run then re-synced

Sync surface:
- `make release-evidence-sync SCENARIO=<id>`
- `make release-evidence-sync-all`
- `python scripts/release_evidence_sync.py --all --preflight`
  - reports `syncable` vs `rerun-needed` against the latest local artifact for each scenario
  - explains common reasons such as payload drift, missing checklist artifact,
    failed latest local run, or tracked-hash mismatch

## Operator Boundary

- LLM may prepare plans, run non-interactive checks, and draft command sequences.
- Interactive manual execution, pass/fail judgment, and evidence acceptance remain human-owned.
- For LLM/agent shell execution, prefer `rtk <command>` when RTK is available.
- Raw commands remain the canonical workflow for humans and CI.
