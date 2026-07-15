# v1.0 Scope Index

_Status: planned · updated 2026-07-15_

This is a planned-scope index, not current runtime documentation. See the active plan for live
status and [`delivery_plan.md`](delivery_plan.md) for the only detailed implementation handoff.

| Slice | User-visible outcome |
|---|---|
| PZ B42.15+ format compatibility — release blocker | Resolve the remaining JSON part of [Issue #1](https://github.com/PlagaMedicum/TranslationZed-py/issues/1) from authoritative game fixtures, while keeping legacy `.txt` projects fully usable and showing actionable errors for unsupported schemas. |
| Git-backed EN synchronization | Preview committed new strings, changed strings, removals, ordering, and comments; merge into drafts without letting the app mutate Git or originals. |
| Add localization | From the locale chooser, acknowledge the official README/forum guidance and safely clone a source locale into a validated new locale. |
| `description.txt` | Edit the complete file through the normal table/detail, cache, status, search, QA, LT, TM, and Save paths. This is independent of locale creation. |
| QA safety pack | Add conservative token-count, leading-whitespace, invalid-character, and duplicate-key checks. |
| LanguageTool | Separate server diagnostics from linguistic findings and expose actionable details, replacements, accepted words, and ignored rules. |
| Machine translation | Show a highlighted, manually requested proposal separate from ranked TM results, with provider-neutral conventional MT and context-aware local LLM adapters for Ollama and llama.cpp-compatible servers. Applying remains undoable and marks `For review`. |
| Release closure | Prove coherence, bounded performance, compatibility, manual workflows, and all three platform packages on the exact v1.0.0 commit. |

No theme expansion is planned. Conventional MT is not exclusive to Google and may use only
documented, licensed provider interfaces. Local model execution remains user-managed outside the
application.
