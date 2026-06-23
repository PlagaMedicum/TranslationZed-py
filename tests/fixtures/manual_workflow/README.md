# Manual workflow fixture set

This fixture supports generic manual scenarios without relying on BE-only files.

Locales:
- `EN` is the immutable source locale.
- `RU` is the primary manual target locale.
- `KO` exists for direct source-reference checks where the requested counterpart
  file is present.

File map:
- `ui.txt`: open/edit/save, TM apply, status-triage
- `menu.txt`: file switching and empty-source verification when the requested KO
  counterpart is missing
- `tm_memory.txt`: deterministic project-TM suggestion source
- `search_scope.txt`: replace-all target in current file and pool
- `search_scope_extra.txt`: locale-scope replace target
- `tzp_status.txt`: status-comment write-back inspection file
