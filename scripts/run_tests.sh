#!/usr/bin/env bash
# Run unit tests; on Linux also run small-round SAT solve tests.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -q -r requirements-dev.txt

echo "==> Unit tests"
python -m pytest tests/ -q -k "not SatSolve"

if [[ "$(uname -s)" == "Linux" && -x bin/cryptominisat5 ]]; then
  echo "==> SAT solve tests (rounds 1–2)"
  python -m pytest tests/test_present.py::TestSatSolveSmallRounds -q
else
  echo "==> Skipping SAT solve tests (need Linux + bin/cryptominisat5)"
fi

echo "All done."
