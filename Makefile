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

# ─── Meta targets ─────────────────────────────────────────────────────────────
.PHONY: venv install precommit fmt fmt-changed fmt-check lint lint-check typecheck arch-check \
	test test-cov test-perf test-perf-heavy perf-advisory check check-local verify verify-ci verify-ci-core verify-ci-bench verify-core \
	verify-heavy verify-heavy-extra verify-fast release-check release-check-if-tag release-dry-run \
	security docstyle docs-build bench bench-check bench-advisory test-mutation \
	test-mutation-stage mutation-promotion-check mutation-promotion-readiness \
	test-warnings run clean clean-cache clean-config perf-scenarios ci-deps dist pack pack-win \
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

lint:
	VENV=$(VENV) bash scripts/lint.sh

lint-check:
	VENV=$(VENV) bash scripts/lint_check.sh

typecheck:
	VENV=$(VENV) bash scripts/typecheck.sh

arch-check:
	VENV=$(VENV) bash scripts/arch_check.sh

test:
	VENV=$(VENV) bash scripts/test.sh

test-cov:
	VENV=$(VENV) ARTIFACTS=$(ARTIFACTS) bash scripts/test_cov.sh

test-perf:
	VENV=$(VENV) bash scripts/test_perf.sh

test-perf-heavy:
	VENV=$(VENV) bash scripts/test_perf_heavy.sh

security:
	VENV=$(VENV) ARTIFACTS=$(ARTIFACTS) bash scripts/security.sh

docstyle:
	VENV=$(VENV) bash scripts/docstyle.sh

docs-build:
	VENV=$(VENV) ARTIFACTS=$(ARTIFACTS) bash scripts/docs_build.sh

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
	$(VENV)/bin/python scripts/mutation_stage.py \
		--stage "$(MUTATION_STAGE)" \
		--min-killed-percent "$(MUTATION_STAGE_MIN_KILLED_PERCENT)" \
		--out-env "$$stage_env" >/dev/null; \
	. "$$stage_env"; \
	$(MAKE) test-mutation \
		MUTATION_SCORE_MODE="$$MUTATION_EFFECTIVE_MODE" \
		MUTATION_MIN_KILLED_PERCENT="$$MUTATION_EFFECTIVE_MIN_KILLED_PERCENT"

mutation-promotion-check:
	$(VENV)/bin/python scripts/check_mutation_promotion.py $(ARGS)

mutation-promotion-readiness:
	@if [ -z "$(MUTATION_PROMOTION_REPO)" ]; then \
		echo "MUTATION_PROMOTION_REPO is required (example: owner/repo)."; \
		exit 2; \
	fi
	$(VENV)/bin/python scripts/check_mutation_promotion_ci.py \
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

test-encoding-integrity:
	VENV=$(VENV) bash scripts/test_encoding_integrity.sh

diagnose-encoding:
	VENV=$(VENV) bash scripts/diagnose_encoding.sh $(if $(ARGS),$(ARGS),tests/fixtures/prod_like)

test-readonly-clean:
	VENV=$(VENV) bash scripts/test_readonly_clean.sh

test-warnings:
	VENV=$(VENV) bash scripts/test_warnings.sh

# ─── Fast dev gates ────────────────────────────────────────────────────────────
## strict non-mutating quality gate (check-only) for CI
check: fmt-check lint-check typecheck arch-check test

## local quality gate (allows auto-fix)
check-local: fmt lint typecheck arch-check test

# ─── Verification umbrella gates ───────────────────────────────────────────────
## full local verification core (auto-fix + warning policy)
verify-core: clean-cache clean-config fmt-changed lint typecheck arch-check perf-advisory \
	bench-advisory test-cov test-readonly-clean security docstyle docs-build

## local perf gates are advisory; strict blocking lives in verify-ci
perf-advisory:
	@$(MAKE) test-perf || { \
		echo "verify warning: test-perf failed (advisory in local verify)."; \
	}
	@$(MAKE) perf-scenarios || { \
		echo "verify warning: perf-scenarios failed (advisory in local verify)."; \
	}

## local benchmark regression is advisory; strict blocking lives in verify-ci
bench-advisory:
	@$(MAKE) bench-check BENCH_COMPARE_MODE=warn || { \
		echo "verify warning: bench-check failed (advisory in local verify)."; \
	}

## full local verification (auto-fix allowed, warn if tracked files changed)
verify:
	@set -e; \
	before="$$(mktemp)"; \
	after="$$(mktemp)"; \
	trap 'rm -f "$$before" "$$after"' EXIT; \
	git status --porcelain --untracked-files=no >"$$before"; \
	$(MAKE) verify-core; \
	$(MAKE) release-check-if-tag TAG=$(TAG); \
	git status --porcelain --untracked-files=no >"$$after"; \
	if ! cmp -s "$$before" "$$after"; then \
		echo "verify warning: auto-fixers changed tracked files. Review and commit updates."; \
		diff -u "$$before" "$$after" || true; \
	fi

## strict CI verification core (non-mutating)
verify-ci-core: clean-cache clean-config fmt-check lint-check typecheck arch-check test-cov test-perf \
	test-readonly-clean security docstyle docs-build perf-scenarios release-check-if-tag

## CI benchmark gate helper; can be skipped when a dedicated benchmark job is used.
verify-ci-bench:
	@if [ "$(VERIFY_SKIP_BENCH)" = "1" ]; then \
		echo "verify-ci: bench-check skipped (VERIFY_SKIP_BENCH=1; use dedicated benchmark gate)."; \
	else \
		$(MAKE) bench-check; \
	fi

## strict CI verification (non-mutating + fail-on-drift)
verify-ci:
	@set -e; \
	before="$$(mktemp)"; \
	after="$$(mktemp)"; \
	trap 'rm -f "$$before" "$$after"' EXIT; \
	git status --porcelain --untracked-files=no >"$$before"; \
	$(MAKE) verify-ci-core TAG=$(TAG); \
	$(MAKE) verify-ci-bench; \
	git status --porcelain --untracked-files=no >"$$after"; \
	if ! cmp -s "$$before" "$$after"; then \
		echo "verify-ci failed: tracked files changed during verification."; \
		diff -u "$$before" "$$after" || true; \
		exit 1; \
	fi

## tiered heavy verification (advisory mutation + optional extra checks)
verify-heavy-extra: test-perf-heavy test-mutation

## tiered heavy verification (strict base + heavy extras)
verify-heavy: verify-ci verify-heavy-extra

## fastest strict developer gate
verify-fast: check

# ─── Release gates ─────────────────────────────────────────────────────────────
## run release-check only when TAG is provided (keeps verify single-command friendly)
release-check-if-tag:
	@if [ -n "$(TAG)" ]; then \
		echo "TAG=$(TAG) detected; running release-check"; \
		$(MAKE) release-check TAG=$(TAG); \
	else \
		echo "release-check skipped (set TAG=vX.Y.Z to include it)"; \
	fi

## validate release tag/version/changelog alignment
release-check:
	TAG=$(TAG) VENV=$(VENV) bash scripts/release_check.sh $(ARGS)

## run release-candidate dry run gates before final tagging
release-dry-run:
	@if [ -z "$(TAG)" ]; then \
		echo "TAG is required (example: make release-dry-run TAG=v0.6.0-rc1)"; \
		exit 2; \
	fi
	$(MAKE) verify TAG=$(TAG)
	$(MAKE) release-check TAG=$(TAG)

# ─── Utilities ─────────────────────────────────────────────────────────────────
## run perf scenarios against fixture translation files
perf-scenarios:
	VENV=$(VENV) bash scripts/perf_scenarios.sh $(ARGS)

## convenience runner: make run ARGS="--help"
run:
	VENV=$(VENV) bash scripts/run.sh $(ARGS)

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
