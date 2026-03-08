"""Randomized stateful contracts for project-session startup/recovery orchestration."""

from __future__ import annotations

from pathlib import Path

from hypothesis import strategies as st
from hypothesis.stateful import RuleBasedStateMachine, rule

from tests.hypothesis_profile import stateful_prop_settings
from translationzed_py.core.project_session import (
    CrashRecoveryAffectedFile,
    CrashRecoveryReport,
    build_crash_recovery_apply_plan,
    build_post_locale_startup_plan,
    execute_crash_recovery_apply_plan,
    run_post_locale_startup_tasks,
)


def _sample_report(root: Path) -> CrashRecoveryReport:
    return CrashRecoveryReport(
        project_root=str(root),
        generated_at_ms=1,
        affected_files=(
            CrashRecoveryAffectedFile(
                file_path="BE/ui.txt",
                locale="BE",
                draft_value_count=2,
                status_only_count=0,
                cache_mtime_ns=1,
                warning="",
            ),
        ),
        total_files=1,
        total_draft_values=2,
        total_status_only=0,
    )


@stateful_prop_settings(
    fast_examples=18,
    slow_examples=72,
    fast_steps=18,
    slow_steps=72,
)
class ProjectSessionStateMachine(RuleBasedStateMachine):
    """Exercise startup ordering and crash decision invariants under random inputs."""

    def __init__(self) -> None:
        """Initialize deterministic root/cache parameters for randomized checks."""
        super().__init__()
        self._root = Path("/tmp/tzp-prop-session")
        self._cache_dir = ".tzp/cache"
        self._cache_ext = ".bin"
        self._snapshot = self._root / self._cache_dir / "session.resume.json"

    @rule(has_locales=st.booleans(), resume_applies=st.booleans())
    def startup_ordering_contract(
        self, has_locales: bool, resume_applies: bool
    ) -> None:
        """Snapshot apply runs before auto-open; fallback runs only when needed."""
        selected_locales = ["BE"] if has_locales else []
        plan = build_post_locale_startup_plan(selected_locales=selected_locales)
        calls: list[str] = []

        def _cache_scan() -> None:
            calls.append("cache_scan")

        def _session_resume() -> bool:
            calls.append("session_resume")
            return resume_applies

        def _auto_open() -> None:
            calls.append("auto_open")

        executed = run_post_locale_startup_tasks(
            plan=plan,
            run_cache_scan=_cache_scan,
            run_session_resume=_session_resume,
            run_auto_open=_auto_open,
        )

        if not has_locales:
            assert not plan.should_schedule
            assert executed == 0
            assert calls == []
            return

        assert plan.should_schedule
        assert calls[:2] == ["cache_scan", "session_resume"]
        if resume_applies:
            assert "auto_open" not in calls
            assert executed == 2
        else:
            assert calls == ["cache_scan", "session_resume", "auto_open"]
            assert executed == 3

    @rule(
        decision=st.sampled_from(("restore", "discard", "cancel")),
        has_report=st.booleans(),
    )
    def crash_decision_contract(self, decision: str, has_report: bool) -> None:
        """Restore/discard/cancel plans preserve UC-12 startup and discard semantics."""
        report = _sample_report(self._root) if has_report else None
        plan = build_crash_recovery_apply_plan(
            root=self._root,
            cache_dir=self._cache_dir,
            cache_ext=self._cache_ext,
            report=report,
            decision=decision,
        )
        assert plan.decision == decision
        if decision == "cancel":
            assert not plan.continue_startup
            assert plan.discard_cache_paths == ()
            return
        assert plan.continue_startup
        if decision == "restore":
            assert plan.discard_cache_paths == ()
            return
        assert self._snapshot in plan.discard_cache_paths
        if has_report:
            assert any(
                path.suffix == self._cache_ext for path in plan.discard_cache_paths
            )

    @rule(fail_snapshot_delete=st.booleans())
    def discard_execution_reports_snapshot_delete_failures(
        self, fail_snapshot_delete: bool
    ) -> None:
        """Discard execution reports snapshot delete failures instead of leaking exceptions."""
        plan = build_crash_recovery_apply_plan(
            root=self._root,
            cache_dir=self._cache_dir,
            cache_ext=self._cache_ext,
            report=None,
            decision="discard",
        )
        assert plan.discard_cache_paths == (self._snapshot,)

        def _unlink(path: Path) -> None:
            if fail_snapshot_delete and path == self._snapshot:
                raise OSError("snapshot unlink failed")

        execution = execute_crash_recovery_apply_plan(
            plan=plan,
            unlink_cache_path=_unlink,
        )
        assert execution.decision == "discard"
        assert execution.continue_startup
        if fail_snapshot_delete:
            assert execution.discarded_cache_paths == ()
            assert execution.failed_cache_paths == (self._snapshot,)
            assert execution.failure_message is not None
            return
        assert execution.discarded_cache_paths == (self._snapshot,)
        assert execution.failed_cache_paths == ()
        assert execution.failure_message is None


TestProjectSessionStateMachine = ProjectSessionStateMachine.TestCase
