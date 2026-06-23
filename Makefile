# Public automation facade for TranslationZed-Py.
# Keep this surface small and stable; detailed orchestration lives in scripts/.

PY      ?= python
VENV    ?= .venv
ARTIFACTS ?= artifacts
BENCH_BASELINE ?= tests/benchmarks/baseline.json
BENCH_CURRENT ?= $(ARTIFACTS)/bench/bench.json
MUTATION_STAGE_MIN_KILLED_PERCENT ?= 25
MUTATION_SCORE_MODE ?= warn
MUTATION_MIN_KILLED_PERCENT ?= 0
MUTATION_STAGE ?= soft
MUTATION_PROMOTION_REPO ?= $(GITHUB_REPOSITORY)
MUTATION_PROMOTION_WORKFLOW ?= ci.yml
MUTATION_PROMOTION_BRANCH ?= main
MUTATION_PROMOTION_EVENT ?= schedule
MUTATION_PROMOTION_ARTIFACT_NAME ?= heavy-mutation-summary
MUTATION_PROMOTION_REQUIRED_CONSECUTIVE ?= 2
MUTATION_PROMOTION_MIN_KILLED_PERCENT ?= 25
MUTATION_PROMOTION_REQUIRE_MODE ?= fail
MUTATION_PROMOTION_TOKEN_ENV ?= GITHUB_TOKEN
MUTATION_PROMOTION_OUT_JSON ?= $(ARTIFACTS)/mutation/promotion-readiness.json
COVERAGE_PROMOTION_REQUIRED_CONSECUTIVE ?= 2
COVERAGE_PROMOTION_MIN_OVERALL ?= 92
COVERAGE_PROMOTION_MIN_CORE ?= 97
COVERAGE_PROMOTION_SUMMARIES ?=
COVERAGE_PROMOTION_OUT_JSON ?= $(ARTIFACTS)/coverage/promotion-readiness.json

.PHONY: \
	venv install precommit \
	gate-dev gate-commit gate-push gate-task-close gate-ci-pr gate-heavy-advisory gate-release \
	test test-core-fast test-cov test-ui-manual-contract arch-check locale-agnostic-check docs-check bench bench-check security \
	test-mutation test-mutation-stage mutation-promotion-check mutation-promotion-readiness coverage-promotion-check \
	ui-manual-list ui-manual-run release-evidence-check release-evidence-sync release-evidence-sync-all \
	run pack pack-win dist ci-deps clean clean-cache clean-config clean-manual-artifacts release-check release-dry-run

venv:
	PY=$(PY) VENV=$(VENV) bash scripts/venv.sh

install:
	VENV=$(VENV) bash scripts/install.sh

precommit: venv
	VENV=$(VENV) bash scripts/precommit.sh

test:
	VENV=$(VENV) bash scripts/test.sh $(ARGS)

arch-check:
	VENV=$(VENV) bash scripts/arch_check.sh $(ARGS)

gate-dev:
	VENV=$(VENV) PY=$(PY) ARTIFACTS=$(ARTIFACTS) bash scripts/gates/gate_dev.sh $(ARGS)

gate-commit:
	VENV=$(VENV) PY=$(PY) ARTIFACTS=$(ARTIFACTS) bash scripts/gates/gate_commit.sh $(ARGS)

gate-push:
	VENV=$(VENV) PY=$(PY) ARTIFACTS=$(ARTIFACTS) bash scripts/gates/gate_push.sh $(ARGS)

gate-task-close:
	VENV=$(VENV) PY=$(PY) ARTIFACTS=$(ARTIFACTS) bash scripts/gates/gate_task_close.sh $(ARGS)

gate-ci-pr:
	VENV=$(VENV) PY=$(PY) ARTIFACTS=$(ARTIFACTS) bash scripts/gates/gate_ci_pr.sh $(ARGS)

gate-heavy-advisory:
	VENV=$(VENV) PY=$(PY) ARTIFACTS=$(ARTIFACTS) MUTATION_STAGE_MIN_KILLED_PERCENT=$(MUTATION_STAGE_MIN_KILLED_PERCENT) \
		bash scripts/gates/gate_heavy_advisory.sh $(ARGS)

gate-release:
	TAG=$(TAG) VENV=$(VENV) PY=$(PY) ARTIFACTS=$(ARTIFACTS) BENCH_BASELINE=$(BENCH_BASELINE) BENCH_CURRENT=$(BENCH_CURRENT) \
		MUTATION_STAGE_MIN_KILLED_PERCENT=$(MUTATION_STAGE_MIN_KILLED_PERCENT) \
		bash scripts/gates/gate_release.sh $(ARGS)

test-core-fast:
	VENV=$(VENV) bash scripts/test_core_fast.sh $(ARGS)

test-cov:
	VENV=$(VENV) ARTIFACTS=$(ARTIFACTS) bash scripts/test_cov.sh $(ARGS)

test-ui-manual-contract:
	VENV=$(VENV) PY=$(PY) bash scripts/run_python.sh scripts/ui_manual_contract_check.py \
		--json-out $(ARTIFACTS)/manual-ui/manual_contract_check.json \
		$(ARGS)

locale-agnostic-check:
	VENV=$(VENV) PY=$(PY) bash scripts/run_python.sh scripts/locale_agnostic_check.py $(ARGS)

docs-check:
	VENV=$(VENV) PY=$(PY) ARTIFACTS=$(ARTIFACTS) bash scripts/gates/docs_check.sh $(ARGS)

bench:
	VENV=$(VENV) ARTIFACTS=$(ARTIFACTS) BENCH_CURRENT=$(BENCH_CURRENT) bash scripts/bench.sh $(ARGS)

bench-check:
	VENV=$(VENV) ARTIFACTS=$(ARTIFACTS) BENCH_BASELINE=$(BENCH_BASELINE) BENCH_CURRENT=$(BENCH_CURRENT) \
		bash scripts/bench_check.sh $(ARGS)

security:
	VENV=$(VENV) ARTIFACTS=$(ARTIFACTS) bash scripts/security.sh $(ARGS)

test-mutation:
	VENV=$(VENV) ARTIFACTS=$(ARTIFACTS) MUTATION_SCORE_MODE=$(MUTATION_SCORE_MODE) \
		MUTATION_MIN_KILLED_PERCENT=$(MUTATION_MIN_KILLED_PERCENT) \
		bash scripts/mutation.sh $(ARGS)

test-mutation-stage:
	VENV=$(VENV) PY=$(PY) ARTIFACTS=$(ARTIFACTS) MUTATION_STAGE=$(MUTATION_STAGE) \
		MUTATION_STAGE_MIN_KILLED_PERCENT=$(MUTATION_STAGE_MIN_KILLED_PERCENT) \
		bash scripts/test_mutation_stage_internal.sh $(ARGS)

mutation-promotion-check:
	VENV=$(VENV) PY=$(PY) bash scripts/run_python.sh scripts/check_mutation_promotion.py $(ARGS)

mutation-promotion-readiness:
	@if [ -z "$(MUTATION_PROMOTION_REPO)" ]; then \
		echo "MUTATION_PROMOTION_REPO is required (example: owner/repo)."; \
		exit 2; \
	fi
	VENV=$(VENV) PY=$(PY) bash scripts/run_python.sh scripts/check_mutation_promotion_ci.py \
		--repo "$(MUTATION_PROMOTION_REPO)" \
		--workflow "$(MUTATION_PROMOTION_WORKFLOW)" \
		--branch "$(MUTATION_PROMOTION_BRANCH)" \
		--event "$(MUTATION_PROMOTION_EVENT)" \
		--artifact-name "$(MUTATION_PROMOTION_ARTIFACT_NAME)" \
		--required-consecutive "$(MUTATION_PROMOTION_REQUIRED_CONSECUTIVE)" \
		--min-killed-percent "$(MUTATION_PROMOTION_MIN_KILLED_PERCENT)" \
		--require-mode "$(MUTATION_PROMOTION_REQUIRE_MODE)" \
		--token-env "$(MUTATION_PROMOTION_TOKEN_ENV)" \
		--out-json "$(MUTATION_PROMOTION_OUT_JSON)" \
		$(ARGS)

coverage-promotion-check:
	@if [ -z "$(COVERAGE_PROMOTION_SUMMARIES)" ]; then \
		echo "COVERAGE_PROMOTION_SUMMARIES is required."; \
		exit 2; \
	fi
	VENV=$(VENV) PY=$(PY) bash scripts/run_python.sh scripts/check_coverage_promotion.py \
		--summaries $(COVERAGE_PROMOTION_SUMMARIES) \
		--required-consecutive "$(COVERAGE_PROMOTION_REQUIRED_CONSECUTIVE)" \
		--min-overall "$(COVERAGE_PROMOTION_MIN_OVERALL)" \
		--min-core "$(COVERAGE_PROMOTION_MIN_CORE)" \
		--out-json "$(COVERAGE_PROMOTION_OUT_JSON)" \
		$(ARGS)

ui-manual-list:
	VENV=$(VENV) PY=$(PY) bash scripts/run_python.sh scripts/ui_manual_runner.py --list $(ARGS)

ui-manual-run:
	@if [ -z "$(SCENARIO)" ]; then \
		echo "SCENARIO is required (example: make ui-manual-run SCENARIO=open-edit-save-basic)"; \
		exit 2; \
	fi
	VENV=$(VENV) PY=$(PY) bash scripts/run_python.sh scripts/ui_manual_runner.py \
		--scenario "$(SCENARIO)" \
		--results-dir "$(ARTIFACTS)/manual-ui" \
		$(ARGS)

release-evidence-check:
	VENV=$(VENV) PY=$(PY) bash scripts/run_python.sh scripts/release_evidence_check.py \
		--json-out $(ARTIFACTS)/release/release_evidence_check.json \
		$(ARGS)

release-evidence-sync:
	@if [ -z "$(SCENARIO)" ]; then \
		echo "SCENARIO is required (example: make release-evidence-sync SCENARIO=open-edit-save-basic)"; \
		exit 2; \
	fi
	VENV=$(VENV) PY=$(PY) bash scripts/run_python.sh scripts/release_evidence_sync.py \
		--scenario "$(SCENARIO)" \
		$(ARGS)

release-evidence-sync-all:
	VENV=$(VENV) PY=$(PY) bash scripts/run_python.sh scripts/release_evidence_sync.py \
		--all \
		$(ARGS)

release-check: release-evidence-check
	TAG=$(TAG) VENV=$(VENV) ARTIFACTS=$(ARTIFACTS) bash scripts/release_check.sh $(ARGS)

release-dry-run:
	@if [ -z "$(TAG)" ]; then \
		echo "TAG is required (example: make release-dry-run TAG=v0.9.0-rc1)"; \
		exit 2; \
	fi
	$(MAKE) gate-release TAG=$(TAG)

run:
	VENV=$(VENV) bash scripts/run.sh $(ARGS)

clean-manual-artifacts:
	VENV=$(VENV) PY=$(PY) bash scripts/run_python.sh scripts/clean_manual_artifacts.py \
		--artifacts-dir "$(ARTIFACTS)/manual-ui" \
		$(ARGS)

clean:
	bash scripts/clean.sh

clean-cache:
	bash scripts/clean_cache.sh

clean-config:
	bash scripts/clean_config.sh

ci-deps:
	bash scripts/ci_deps_linux.sh

dist: clean
	VENV=$(VENV) bash scripts/dist.sh

pack: clean
	VENV=$(VENV) bash scripts/pack.sh

pack-win:
	pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/pack.ps1
