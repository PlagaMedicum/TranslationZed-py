# ─── Configurable vars ────────────────────────────────────────────────────────
PY      ?= python            # override on CLI:  make PY=python3.12 venv
PIP     ?= $(PY) -m pip
VENV    ?= .venv
VENV_ACT = . $(VENV)/bin/activate &&

# ─── Meta targets ─────────────────────────────────────────────────────────────
.PHONY: venv install precommit fmt lint typecheck test check run clean dist

## create .venv and populate dev deps (one-off)
venv:
	@if [ ! -d $(VENV) ]; then \
	    $(PY) -m venv $(VENV); \
	    source $(VENV_ACT); \
	    $(VENV_ACT) $(PY) -m pip install -U pip; \
	    $(VENV_ACT) $(PIP) install -e .[dev]; \
	else \
	    echo "$(VENV) already exists — skip creation"; \
	fi

## (re)install the package in editable mode inside existing venv
install:
	@if [ ! -d $(VENV) ]; then \
	    echo "No venv; run 'make venv' first"; exit 1; \
	fi
	$(VENV_ACT) $(PIP) install -e .

## install pre-commit hooks (only once per clone)
precommit: venv
	$(VENV_ACT) pre-commit install

fmt:
	$(VENV_ACT) black translationzed_py tests

lint:
	$(VENV_ACT) ruff check translationzed_py tests --fix

typecheck:
	$(VENV_ACT) mypy translationzed_py

test:
	$(VENV_ACT) pytest -q

## run all quality gates
check: fmt lint typecheck test

## convenience runner:  make run ARGS="--help"
run:
	$(VENV_ACT) $(PY) -m translationzed_py $(ARGS)

clean:
	rm -rf build dist *.egg-info
	find . -type d \( -name "__pycache__" -o -name ".mypy_cache" -o -name ".ruff_cache" -o -name ".pytest_cache" \) -exec rm -rf {} +

dist: clean
	$(PY) -m build --wheel --sdist
