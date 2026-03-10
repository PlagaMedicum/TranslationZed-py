# ─── Configurable vars ────────────────────────────────────────────────────────
PY      ?= python            # override on CLI: make PY=python3.12 venv
VENV    ?= .venv
ARTIFACTS ?= artifacts
BENCH_BASELINE ?= tests/benchmarks/baseline.json
BENCH_CURRENT ?= $(ARTIFACTS)/bench/bench.json
MUTATION_SCORE_MODE ?= warn
MUTATION_MIN_KILLED_PERCENT ?= 0
MUTATION_STAGE ?= soft
MUTATION_STAGE_MIN_KILLED_PERCENT ?= 25
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

# ─── Meta targets ─────────────────────────────────────────────────────────────
.PHONY: venv install precommit fmt fmt-changed fmt-check fmt-check-changed lint lint-check typecheck arch-check locale-agnostic-check \
	test test-cov test-core-fast test-routed-fast test-routed-full test-prop-fast test-prop-slow test-search-a35 test-search-a37 test-status-a34 test-qa-v09 test-tmq-v09 test-tmw-v09 test-cr-v09 test-src-a29 test-tzp-a30 test-ui-manual-contract test-a31-manual test-perf test-perf-scale test-perf-heavy \
	gate-dev gate-commit gate-push gate-task-close gate-ci-pr gate-heavy-advisory gate-release release-check release-dry-run release-evidence-check \
	security docstyle docs-build docs-build-lite docs-index docs-api docs-contract docs-check code-triage review-queue-check \
	docs-index-write \
	bench bench-check test-mutation \
	test-mutation-stage mutation-promotion-check mutation-promotion-readiness \
	test-cov-promotion-contract coverage-promotion-check \
	test-warnings run ui-manual-list ui-manual-run ui-manual-headless ui-manual-batch clean clean-cache clean-config perf-scenarios perf-dependency-eval ci-deps dist pack pack-win \
	test-encoding-integrity diagnose-encoding test-readonly-clean

# ─── Environment/bootstrap ─────────────────────────────────────────────────────
## create .venv and populate dev deps (one-off)
venv:
	PY=$(PY) VENV=$(VENV) bash scripts/venv.sh

## (re)install the package in editable mode inside existing venv
install:
	VENV=$(VENV) bash scripts/install.sh

## install pre-commit hooks (only once per clone)
precommit: venv
	VENV=$(VENV) bash scripts/precommit.sh

# ─── Quality families ──────────────────────────────────────────────────────────
fmt:
	VENV=$(VENV) bash scripts/fmt.sh

fmt-changed:
	FMT_SCOPE=changed VENV=$(VENV) bash scripts/fmt.sh

fmt-check:
	VENV=$(VENV) bash scripts/fmt_check.sh

fmt-check-changed:
	FMT_SCOPE=changed VENV=$(VENV) bash scripts/fmt_check.sh

lint:
	VENV=$(VENV) bash scripts/lint.sh

lint-check:
	VENV=$(VENV) bash scripts/lint_check.sh

typecheck:
	VENV=$(VENV) bash scripts/typecheck.sh

arch-check:
	VENV=$(VENV) bash scripts/arch_check.sh

locale-agnostic-check:
	VENV=$(VENV) PY=$(PY) bash scripts/run_python.sh scripts/locale_agnostic_check.py $(ARGS)

test:
	VENV=$(VENV) bash scripts/test.sh

test-cov:
	VENV=$(VENV) ARTIFACTS=$(ARTIFACTS) bash scripts/test_cov.sh

test-core-fast:
	VENV=$(VENV) bash scripts/test_core_fast.sh $(ARGS)

test-routed-fast:
	@set -e; \
	targets="$$(VENV=$(VENV) PY=$(PY) bash scripts/run_python.sh scripts/select_test_targets.py --mode fast --output shell $(ARGS))"; \
	if [ -z "$$targets" ]; then \
		echo "test-routed-fast: no packet lanes matched changed files."; \
	else \
		for target in $$targets; do \
			echo "test-routed-fast: running $$target"; \
			$(MAKE) "$$target"; \
		done; \
	fi

test-routed-full:
	@set -e; \
	targets="$$(VENV=$(VENV) PY=$(PY) bash scripts/run_python.sh scripts/select_test_targets.py --mode full --output shell $(ARGS))"; \
	for target in $$targets; do \
		echo "test-routed-full: running $$target"; \
		$(MAKE) "$$target"; \
	done

test-prop-fast:
	VENV=$(VENV) bash scripts/test_prop_fast.sh $(ARGS)

test-prop-slow:
	VENV=$(VENV) bash scripts/test_prop_slow.sh $(ARGS)

test-search-a35:
	VENV=$(VENV) bash scripts/test_search_a35.sh $(ARGS)

test-search-a37:
	VENV=$(VENV) bash scripts/test_search_a37.sh $(ARGS)

test-status-a34:
	VENV=$(VENV) bash scripts/test_status_a34.sh $(ARGS)

test-cov-promotion-contract:
	VENV=$(VENV) bash scripts/test_cov_promotion_contract.sh $(ARGS)

test-qa-v09:
	VENV=$(VENV) bash scripts/test_qa_v09.sh $(ARGS)

test-tmq-v09:
	VENV=$(VENV) bash scripts/test_tmq_v09.sh $(ARGS)

test-tmw-v09:
	VENV=$(VENV) bash scripts/test_tmw_v09.sh $(ARGS)

test-cr-v09:
	VENV=$(VENV) bash scripts/test_cr_v09.sh $(ARGS)

test-src-a29:
	VENV=$(VENV) bash scripts/test_src_a29.sh $(ARGS)

test-tzp-a30:
	VENV=$(VENV) bash scripts/test_tzp_a30.sh $(ARGS)

test-ui-manual-contract:
	VENV=$(VENV) PY=$(PY) bash scripts/run_python.sh scripts/ui_manual_contract_check.py $(ARGS)

test-a31-manual:
	VENV=$(VENV) bash scripts/test_a31_manual.sh $(ARGS)

test-perf:
	VENV=$(VENV) bash scripts/test_perf.sh

test-perf-scale:
	VENV=$(VENV) bash scripts/test_perf_scale.sh

test-perf-heavy:
	VENV=$(VENV) bash scripts/test_perf_heavy.sh

security:
	VENV=$(VENV) ARTIFACTS=$(ARTIFACTS) bash scripts/security.sh

docstyle:
	VENV=$(VENV) bash scripts/docstyle.sh

docs-build:
	VENV=$(VENV) ARTIFACTS=$(ARTIFACTS) bash scripts/docs_build.sh

docs-build-lite:
	DOCS_BUILD_MODE=lite VENV=$(VENV) ARTIFACTS=$(ARTIFACTS) bash scripts/docs_build.sh

docs-index:
	VENV=$(VENV) PY=$(PY) bash scripts/run_python.sh scripts/generate_contract_index.py --check \
		--out docs/reference/contract_index.json

docs-index-write:
	VENV=$(VENV) PY=$(PY) bash scripts/run_python.sh scripts/generate_contract_index.py --write \
		--out docs/reference/contract_index.json

docs-api: docs-index
	@echo "docs-api: mkdocstrings API pages validated through docs-index + docs-build"

review-queue-check:
	VENV=$(VENV) PY=$(PY) bash scripts/run_python.sh scripts/review_queue_check.py \
		--queue docs/reference/review_queue.json

code-triage:
	VENV=$(VENV) PY=$(PY) bash scripts/run_python.sh scripts/code_quality_triage.py \
		--review-queue docs/reference/review_queue.json \
		--out-json $(ARTIFACTS)/docs/code_triage_report.json \
		--pass-log $(ARTIFACTS)/docs/triage_pass_log.json $(ARGS)

docs-contract: review-queue-check code-triage
	VENV=$(VENV) PY=$(PY) bash scripts/run_python.sh scripts/docs_contract_check.py --site-root $(ARTIFACTS)/docs/site

docs-check: docstyle docs-build docs-index docs-api docs-contract locale-agnostic-check

bench:
	VENV=$(VENV) ARTIFACTS=$(ARTIFACTS) BENCH_CURRENT=$(BENCH_CURRENT) \
		bash scripts/bench.sh $(ARGS)

bench-check:
	VENV=$(VENV) ARTIFACTS=$(ARTIFACTS) BENCH_BASELINE=$(BENCH_BASELINE) BENCH_CURRENT=$(BENCH_CURRENT) \
		bash scripts/bench_check.sh $(ARGS)

test-mutation:
	VENV=$(VENV) ARTIFACTS=$(ARTIFACTS) MUTATION_SCORE_MODE=$(MUTATION_SCORE_MODE) \
		MUTATION_MIN_KILLED_PERCENT=$(MUTATION_MIN_KILLED_PERCENT) \
		bash scripts/mutation.sh

test-mutation-stage:
	@set -e; \
	stage_env="$$(mktemp)"; \
	trap 'rm -f "$$stage_env"' EXIT; \
	VENV=$(VENV) PY=$(PY) bash scripts/run_python.sh scripts/mutation_stage.py \
		--stage "$(MUTATION_STAGE)" \
		--min-killed-percent "$(MUTATION_STAGE_MIN_KILLED_PERCENT)" \
		--out-env "$$stage_env" >/dev/null; \
	. "$$stage_env"; \
	$(MAKE) test-mutation \
		MUTATION_SCORE_MODE="$$MUTATION_EFFECTIVE_MODE" \
		MUTATION_MIN_KILLED_PERCENT="$$MUTATION_EFFECTIVE_MIN_KILLED_PERCENT"

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
		echo "COVERAGE_PROMOTION_SUMMARIES is required (example: make coverage-promotion-check COVERAGE_PROMOTION_SUMMARIES='artifacts/coverage/run1.json artifacts/coverage/run2.json')"; \
		exit 2; \
	fi
	VENV=$(VENV) PY=$(PY) bash scripts/run_python.sh scripts/check_coverage_promotion.py \
		--summaries $(COVERAGE_PROMOTION_SUMMARIES) \
		--required-consecutive "$(COVERAGE_PROMOTION_REQUIRED_CONSECUTIVE)" \
		--min-overall "$(COVERAGE_PROMOTION_MIN_OVERALL)" \
		--min-core "$(COVERAGE_PROMOTION_MIN_CORE)" \
		--out-json "$(COVERAGE_PROMOTION_OUT_JSON)" \
		$(ARGS)

test-encoding-integrity:
	VENV=$(VENV) bash scripts/test_encoding_integrity.sh

diagnose-encoding:
	VENV=$(VENV) bash scripts/diagnose_encoding.sh $(if $(ARGS),$(ARGS),tests/fixtures/prod_like)

test-readonly-clean:
	VENV=$(VENV) bash scripts/test_readonly_clean.sh

test-warnings:
	VENV=$(VENV) bash scripts/test_warnings.sh

# ─── Layered policy gates ─────────────────────────────────────────────────────
## L0 regular dev loop
gate-dev: fmt-check-changed lint-check typecheck arch-check locale-agnostic-check

## L1 pre-commit (hook target)
gate-commit: gate-dev test-ui-manual-contract

## L2 pre-push (hook target)
gate-push: gate-commit test-core-fast test-routed-fast test-readonly-clean

## L3 task-close / docs-close gate
gate-task-close: gate-push test-cov docs-check test-perf-scale

## L4 strict CI gate for push/PR
gate-ci-pr: clean-cache clean-config fmt-check lint-check typecheck arch-check locale-agnostic-check \
	test-ui-manual-contract test-core-fast test-cov \
	test-readonly-clean security docs-check test-perf-scale

## L5 heavy advisory lane (scheduled/manual)
gate-heavy-advisory:
	@$(MAKE) test-prop-slow || { \
		echo "gate-heavy-advisory warning: test-prop-slow failed (advisory)."; \
	}
	@$(MAKE) test-perf-heavy || { \
		echo "gate-heavy-advisory warning: test-perf-heavy failed (advisory)."; \
	}
	@$(MAKE) test-mutation-stage MUTATION_STAGE=soft MUTATION_STAGE_MIN_KILLED_PERCENT=$(MUTATION_STAGE_MIN_KILLED_PERCENT) || { \
		echo "gate-heavy-advisory warning: mutation lane failed (advisory)."; \
	}

## L6 release-tag strict gate
gate-release:
	@if [ -z "$(TAG)" ]; then \
		echo "TAG is required (example: make gate-release TAG=v0.9.0-rc1)"; \
		exit 2; \
	fi
	$(MAKE) gate-ci-pr
	$(MAKE) bench-check BENCH_COMPARE_MODE=fail BENCH_REGRESSION_THRESHOLD_PERCENT=20
	$(MAKE) test-prop-slow
	$(MAKE) test-perf-heavy
	$(MAKE) test-mutation-stage MUTATION_STAGE=strict MUTATION_STAGE_MIN_KILLED_PERCENT=$(MUTATION_STAGE_MIN_KILLED_PERCENT)
	$(MAKE) release-check TAG=$(TAG)

# ─── Release checks ───────────────────────────────────────────────────────────
## validate release tag/version/changelog alignment
release-check: release-evidence-check
	TAG=$(TAG) VENV=$(VENV) bash scripts/release_check.sh $(ARGS)

release-evidence-check:
	VENV=$(VENV) PY=$(PY) bash scripts/run_python.sh scripts/release_evidence_check.py $(ARGS)

## run release-candidate dry run gates before final tagging
release-dry-run:
	@if [ -z "$(TAG)" ]; then \
		echo "TAG is required (example: make release-dry-run TAG=v0.9.0-rc1)"; \
		exit 2; \
	fi
	$(MAKE) gate-release TAG=$(TAG)

# ─── Utilities ─────────────────────────────────────────────────────────────────
## run perf scenarios against fixture translation files
perf-scenarios:
	VENV=$(VENV) bash scripts/perf_scenarios.sh $(ARGS)

perf-dependency-eval:
	VENV=$(VENV) PY=$(PY) bash scripts/run_python.sh scripts/perf_dependency_eval.py $(ARGS)

## convenience runner: make run ARGS="--help"
run:
	VENV=$(VENV) bash scripts/run.sh $(ARGS)

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

ui-manual-headless:
	@if [ -z "$(SCENARIO)" ]; then \
		echo "SCENARIO is required (example: make ui-manual-headless SCENARIO=open-edit-save-basic RESULT=passed)"; \
		exit 2; \
	fi
	@if [ -z "$(RESULT)" ]; then \
		echo "RESULT is required (allowed: passed|failed)"; \
		exit 2; \
	fi
	VENV=$(VENV) PY=$(PY) bash scripts/run_python.sh scripts/ui_manual_runner.py \
		--scenario "$(SCENARIO)" \
		--results-dir "$(ARTIFACTS)/manual-ui" \
		--headless-result "$(RESULT)" \
		$(ARGS)

ui-manual-batch:
	@if [ -z "$(SCENARIOS)" ]; then \
		echo "SCENARIOS is required (example: make ui-manual-batch SCENARIOS=open-edit-save-basic,qa-checklist-manual-run)"; \
		exit 2; \
	fi
	VENV=$(VENV) PY=$(PY) bash scripts/run_python.sh scripts/ui_manual_runner.py \
		--batch "$(SCENARIOS)" \
		--results-dir "$(ARTIFACTS)/manual-ui" \
		$(ARGS)

# ─── Maintenance/packaging ─────────────────────────────────────────────────────
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
