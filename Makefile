# ─── Configurable vars ────────────────────────────────────────────────────────
PY      ?= python            # override on CLI:  make PY=python3.12 venv
VENV    ?= .venv

# ─── Meta targets ─────────────────────────────────────────────────────────────
.PHONY: venv install precommit fmt lint typecheck arch-check test check verify verify-core verify-fast release-check release-check-if-tag release-dry-run run clean clean-cache clean-config perf-scenarios ci-deps dist pack pack-win test-encoding-integrity diagnose-encoding test-readonly-clean

## create .venv and populate dev deps (one-off)
venv:
	PY=$(PY) VENV=$(VENV) bash scripts/venv.sh

## (re)install the package in editable mode inside existing venv
install:
	VENV=$(VENV) bash scripts/install.sh

## install pre-commit hooks (only once per clone)
precommit: venv
	VENV=$(VENV) bash scripts/precommit.sh

fmt:
	VENV=$(VENV) bash scripts/fmt.sh

lint:
	VENV=$(VENV) bash scripts/lint.sh

typecheck:
	VENV=$(VENV) bash scripts/typecheck.sh

arch-check:
	VENV=$(VENV) bash scripts/arch_check.sh

test:
	VENV=$(VENV) bash scripts/test.sh

test-encoding-integrity:
	VENV=$(VENV) bash scripts/test_encoding_integrity.sh

diagnose-encoding:
	VENV=$(VENV) bash scripts/diagnose_encoding.sh $(if $(ARGS),$(ARGS),tests/fixtures/prod_like)

test-readonly-clean:
	VENV=$(VENV) bash scripts/test_readonly_clean.sh

## run all quality gates
check: fmt lint typecheck arch-check test

## pre-commit core verification (clean fixtures + full quality gates)
verify-core: clean-cache clean-config check test-encoding-integrity diagnose-encoding test-readonly-clean

## fastest full developer gate (no cache/config cleanup, no perf scenarios)
verify-fast: check

## full verification (core gate + perf scenarios)
verify: verify-core perf-scenarios release-check-if-tag

## run release-check only when TAG is provided (keeps `make verify` single-command friendly)
release-check-if-tag:
	@if [ -n "$(TAG)" ]; then \
		echo "TAG=$(TAG) detected; running release-check"; \
		$(MAKE) release-check TAG=$(TAG); \
	else \
		echo "release-check skipped (set TAG=vX.Y.Z to include it in make verify)"; \
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
	$(MAKE) verify
	$(MAKE) release-check TAG=$(TAG)

## run perf scenarios against fixture translation files
perf-scenarios:
	VENV=$(VENV) bash scripts/perf_scenarios.sh $(ARGS)

## convenience runner:  make run ARGS="--help"
run:
	VENV=$(VENV) bash scripts/run.sh $(ARGS)

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
