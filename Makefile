# ─── Configurable vars ────────────────────────────────────────────────────────
PY      ?= python            # override on CLI:  make PY=python3.12 venv
PIP     ?= $(PY) -m pip
VENV    ?= .venv
VENV_ACT = . $(VENV)/bin/activate &&

# ─── Meta targets ─────────────────────────────────────────────────────────────
.PHONY: venv install precommit fmt lint typecheck test check verify run clean clean-cache clean-config perf-scenarios ci-deps dist pack pack-win

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

test:
	VENV=$(VENV) bash scripts/test.sh

## run all quality gates
check: fmt lint typecheck test

## pre-commit verification (cleans caches + runs full checks + perf scenarios)
verify: clean-cache clean-config check perf-scenarios

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
