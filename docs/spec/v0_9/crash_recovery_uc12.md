# Crash Recovery Contract (UC-12)
_Updated: 2026-07-15_

## 1) Purpose

Activate crash recovery UX with explicit startup decisions.

History note: v0.9.0 shipped the report/decision policy and dialogs, but the production GUI passed
a constant clean-session signal, so crash-triggered recovery could not activate. The
`session.lock` lifecycle in this current contract is the implemented `dev`/v1.0 reliability fix;
it must not be back-claimed as working in the v0.9.0 release artifact.

## 2) Detection Contract

A recovery flow is triggered when all conditions hold:
1. startup/open project request accepted,
2. recovery-eligible draft cache entries exist,
3. previous session ended uncleanly or cache-draft integrity marker indicates interrupted flow.

The implemented unclean signal is the project-scoped
`<root>/<cache_dir>/session.lock`: successful replacement of a stale `QLockFile` marker sets the
signal. A live owner blocks the second open instead of being treated as stale. The lock uses
long-lived mode, so age alone cannot evict a live project session.

## 3) Dialog Contract (Required Actions)

Actions:
1. `Restore`
2. `Discard`
3. `Cancel`

Additional requirement:
- Same window contains plaintext review/details section describing affected files and counts.

## 4) Decision Semantics

1. `Restore`
   - load recovered draft cache state,
   - continue project open flow.
2. `Discard`
   - permanently delete recovery-eligible cache entries (scoped to current project),
   - delete project session snapshot cache file (`session.resume.json`),
   - continue project open flow with clean state.
3. `Cancel`
   - abort open flow,
   - no mutation to original locale files.

### 4.1 Session Resume Startup Contract

1. Session resume snapshot file is project-scoped cache data:
   - `<root>/<cache_dir>/session.resume.json`.
2. Startup post-locale order is fixed:
   - cache scan,
   - session-resume apply,
   - auto-open fallback only when snapshot does not restore file context.
3. Snapshot schema is versioned and strictly validated; invalid or unknown-version payloads are ignored safely.

## 5) Safety Invariants

1. No-write-on-open remains true.
2. Discard must require explicit user action in recovery dialog.
3. Restore/discard operations must be deterministic and idempotent for repeated startup attempts.
4. Session-resume apply must remain startup-only and must not bypass no-write-on-open guarantees.
5. Acquire the session lock before EN hash/cache migration or other project-persistence writes.
6. Release the lock only after close passes save/cancel guards and the final persistence sequence
   completes; log non-draft snapshot failures without claiming that they prevent close.

## 6) Recovery Report Schema

```text
CrashRecoveryReport {
  project_root: str,
  generated_at_ms: int,
  affected_files: list[
    {
      file_path: str,
      locale: str,
      draft_value_count: int,
      status_only_count: int,
      cache_mtime_ns: int,
      warning: str
    }
  ],
  total_files: int,
  total_draft_values: int,
  total_status_only: int
}
```

## 7) Startup Sequence

```mermaid
sequenceDiagram
  participant APP as startup
  participant LOCK as session.lock
  participant PS as project_session
  participant SR as session_resume
  participant CR as recovery_service
  participant UI as recovery_dialog

  APP->>LOCK: try long-lived one-writer lock
  alt live owner
    LOCK-->>APP: reject open + owner details
  else acquired after stale marker
    LOCK-->>APP: previous_session_unclean=true
  else clean acquisition
    LOCK-->>APP: previous_session_unclean=false
  end
  APP->>PS: build startup plan
  PS->>CR: detect recovery candidates
  CR-->>APP: CrashRecoveryReport | none
  APP->>UI: show Restore/Discard/Cancel + plaintext details
  UI-->>APP: user decision
  APP->>CR: apply decision
  APP->>SR: read/validate session snapshot
  APP->>PS: apply snapshot first, auto-open fallback if needed
  APP->>PS: continue or abort startup flow
```

## 8) Acceptance Scenarios

1. Recovery candidates found, user chooses `Restore`:
   - drafts visible post-open,
   - original files unchanged.
2. Recovery candidates found, user chooses `Discard`:
   - recovery cache removed,
   - project opens without recovered drafts.
3. User chooses `Cancel`:
   - open is aborted,
   - no file/caches unexpectedly mutated.
4. No recovery candidates:
   - no dialog shown.
5. Session snapshot valid:
   - startup restores workspace state/file context first,
   - last-opened fallback is skipped when context is restored.
6. Session snapshot invalid/unknown version:
   - snapshot ignored without exception leakage,
   - startup continues with last-opened fallback behavior.
7. A second live process opens the same project:
   - startup aborts before other project persistence,
   - the first session and its drafts remain untouched.
8. Previous process left a stale session lock and draft cache:
   - stale acquisition marks the session unclean,
   - recovery dialog is shown with the affected draft counts.

## 9) Rollback / Failure Handling

1. If discard operation fails for some files, surface warning with failed paths and keep safe abort option.
2. If restore load fails, surface warning and allow retry/discard/cancel decision.
3. If the session lock cannot be created because of permissions or IO failure, abort project open
   with an actionable error; do not continue without the one-writer guarantee.
