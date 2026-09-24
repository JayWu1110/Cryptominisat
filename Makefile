.PHONY: test test-unit test-sat bench present-tv venv

PYTHON ?= python3
VENV ?= .venv
PIP := $(VENV)/bin/pip
PYTEST := $(VENV)/bin/python -m pytest
PY := $(VENV)/bin/python

venv:
	$(PYTHON) -m venv $(VENV)
	$(PIP) install -q -r requirements-dev.txt

test: venv test-unit test-sat

test-unit: venv
	$(PYTEST) tests/ -q -k "not SatSolve"

test-sat: venv
	chmod +x bin/cryptominisat5 2>/dev/null || true
	$(PYTEST) tests/test_present.py::TestSatSolveSmallRounds -q

bench:
	chmod +x bin/cryptominisat5 2>/dev/null || true
	$(PYTHON) scripts/benchmark.py --rounds 1,2,3,4,5 --maxtime 30

present-tv:
	$(PYTHON) scripts/present80.py
