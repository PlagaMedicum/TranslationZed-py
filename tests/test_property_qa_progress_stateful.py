"""Randomized stateful contracts for QA rule-progress transitions."""

from __future__ import annotations

from hypothesis import strategies as st
from hypothesis.stateful import RuleBasedStateMachine, invariant, rule

from tests.hypothesis_profile import stateful_prop_settings
from translationzed_py.core.qa_service import (
    QA_RULE_ORDER,
    QARuleState,
    build_qa_progress_records,
    qa_completion_ratio,
    transition_qa_rule_state,
)


@stateful_prop_settings(
    fast_examples=18,
    slow_examples=80,
    fast_steps=22,
    slow_steps=88,
)
class QAProgressStateMachine(RuleBasedStateMachine):
    """Exercise legal and illegal QA transitions under randomized operation sequences."""

    def __init__(self) -> None:
        """Initialize one QA run model used across randomized transitions."""
        super().__init__()
        self._run_id = "run-prop"
        self._records = build_qa_progress_records(run_id=self._run_id)
        self._timestamp = 100
        self._last_ratio = qa_completion_ratio(self._records)

    def _record_for(self, rule_id: str):
        return next(record for record in self._records if record.rule_id == rule_id)

    @rule(
        rule_id=st.sampled_from(QA_RULE_ORDER),
        terminal=st.sampled_from(
            (QARuleState.DONE, QARuleState.SKIPPED, QARuleState.FAILED)
        ),
        findings_count=st.integers(min_value=0, max_value=25),
    )
    def legal_transition_steps(
        self,
        rule_id: str,
        terminal: QARuleState,
        findings_count: int,
    ) -> None:
        """Advance a queued/running rule legally and keep ratio monotonic."""
        current = self._record_for(rule_id)
        if current.state == QARuleState.QUEUED:
            self._timestamp += 1
            self._records = transition_qa_rule_state(
                records=self._records,
                run_id=self._run_id,
                rule_id=rule_id,
                new_state=QARuleState.RUNNING,
                timestamp_ms=self._timestamp,
            )
        elif current.state == QARuleState.RUNNING:
            self._timestamp += 1
            self._records = transition_qa_rule_state(
                records=self._records,
                run_id=self._run_id,
                rule_id=rule_id,
                new_state=terminal,
                timestamp_ms=self._timestamp,
                findings_count=findings_count,
            )
        ratio = qa_completion_ratio(self._records)
        assert ratio + 1e-12 >= self._last_ratio
        self._last_ratio = ratio

    @rule(rule_id=st.sampled_from(QA_RULE_ORDER))
    def reject_illegal_state_jumps(self, rule_id: str) -> None:
        """Reject illegal transitions for each current state category."""
        current = self._record_for(rule_id)
        if current.state == QARuleState.QUEUED:
            illegal_target = QARuleState.DONE
        elif current.state == QARuleState.RUNNING:
            illegal_target = QARuleState.QUEUED
        else:
            illegal_target = QARuleState.RUNNING
        try:
            transition_qa_rule_state(
                records=self._records,
                run_id=self._run_id,
                rule_id=rule_id,
                new_state=illegal_target,
                timestamp_ms=self._timestamp + 1,
            )
        except ValueError:
            return
        raise AssertionError("illegal transition unexpectedly accepted")

    @rule(rule_id=st.sampled_from(QA_RULE_ORDER))
    def reject_second_running_transition(self, rule_id: str) -> None:
        """Reject any second running transition for the same rule in one run."""
        current = self._record_for(rule_id)
        if current.state == QARuleState.QUEUED:
            self._timestamp += 1
            self._records = transition_qa_rule_state(
                records=self._records,
                run_id=self._run_id,
                rule_id=rule_id,
                new_state=QARuleState.RUNNING,
                timestamp_ms=self._timestamp,
            )
        try:
            transition_qa_rule_state(
                records=self._records,
                run_id=self._run_id,
                rule_id=rule_id,
                new_state=QARuleState.RUNNING,
                timestamp_ms=self._timestamp + 1,
            )
        except ValueError:
            return
        raise AssertionError("second running transition unexpectedly accepted")

    @invariant()
    def ratio_and_order_invariants(self) -> None:
        """Rule order is fixed and completion ratio stays within bounds."""
        assert tuple(record.rule_id for record in self._records) == QA_RULE_ORDER
        ratio = qa_completion_ratio(self._records)
        assert 0.0 <= ratio <= 1.0


TestQAProgressStateMachine = QAProgressStateMachine.TestCase
