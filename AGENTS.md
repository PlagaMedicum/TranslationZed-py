@/home/plagamed/.codex/RTK.md

# TranslationZed-Py Agent Instructions

## Start Narrow

- Begin with `git status`, the current diff, and targeted `rg`.
- Read `docs/reference/quick_context.md`, then only the authority document relevant to the task.
- Use `docs/meta/docs_structure.md` when ownership is unclear.
- Preserve unrelated user work and avoid broad normalization.

## Engineering Boundaries

- Keep Qt and widget code in `translationzed_py/gui/`.
- Keep workflow and domain policy Qt-free in `translationzed_py/core/`.
- Preserve deterministic behavior, byte-exact structure outside edited literals,
  no-write-on-open safety, locale encoding fidelity, and bounded resource use.
- Prefer direct fixes and narrow ownership. Add abstractions only when they remove proven
  duplication, enforce a boundary, or prevent a repeated failure.

## Documentation And Verification

- Update the canonical owner of changed behavior; update summaries only when they become inaccurate.
- Keep durable interfaces, invariants, failure modes, and operational lessons. Do not duplicate
  ordinary implementation detail across documents.
- Use the narrowest relevant test first, then broaden according to risk.
- Prefer stable Make targets and `rtk` for agent shell work.

## Ask First

Ask before destructive edits, broad refactors, dependency changes, network use, package installs,
git-history changes, or cleanup of release/manual evidence.
