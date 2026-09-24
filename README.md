# PRESENT Algebraic Cryptanalysis with CryptoMiniSat

Recover the **PRESENT-80** master key from a known plaintext/ciphertext pair by encoding the cipher (and key schedule) as a SAT instance and solving it with [CryptoMiniSat](https://github.com/msoos/cryptominisat).

This is an algebraic-cryptanalysis experiment workspace: Python generates DIMACS CNF; CryptoMiniSat searches for a satisfying assignment of the 80-bit key.

> **Honest scope:** truncated rounds (1–2) solve quickly and validate the encoding. Full **31-round** key recovery via plain SAT is **not** expected to finish in practice. See the [experiment report](docs/experiment-report.md) and [benchmark results](results/README.md).

## Requirements

| Component | Notes |
|-----------|--------|
| Python 3 | Stdlib for core scripts; `pytest` for tests (`requirements-dev.txt`) |
| Linux x86-64 | Bundled solver binary is a **static** ELF for this platform |
| CryptoMiniSat 5.x | Prebuilt at `bin/cryptominisat5` (v5.13.0), or install your own |

## Repository layout

```text
.
├── bin/cryptominisat5              # Prebuilt CryptoMiniSat CLI (Linux amd64)
├── lib/                            # Static libraries (optional; for linking)
├── scripts/
│   ├── gen_present_cnf.py          # CNF generator (enc + PRESENT-80 key schedule)
│   ├── present80.py                # Reference cipher (CNF + paper semantics)
│   ├── extract_key.py              # Master key from solver s/v lines
│   ├── verify_solution.py          # Check recovered key vs testcase
│   ├── make_testcase.py            # Build PT/CT from a known key
│   ├── benchmark.py                # Timed gen+solve → results/
│   └── run_tests.sh                # Local test runner
├── tests/                          # pytest unit + small-round SAT tests
├── data/testcases/                 # Plaintext / ciphertext bitstrings
├── out/cnf/, out/solutions/        # Generated artifacts (gitignored)
├── results/                        # Benchmark CSV + markdown table
├── docs/experiment-report.md       # Experiment write-up
├── archive/gen_present_cnf_v1.py   # Older generator (no key schedule)
├── .github/workflows/ci.yml
├── Makefile
├── LICENSE                         # MIT
├── THIRD_PARTY.md
└── README.md
```

## Build / install the solver

This repo does **not** compile CryptoMiniSat from source. Pick one option:

### Option A — use the bundled binary (recommended for Linux amd64)

```bash
chmod +x bin/cryptominisat5
./bin/cryptominisat5 --version
```

You should see CryptoMiniSat version output (bundled build: **5.13.0**).

### Option B — install CryptoMiniSat yourself

- Release binaries: https://github.com/msoos/cryptominisat/releases  
- Or build from source (CMake): https://github.com/msoos/cryptominisat  

Then put `cryptominisat5` on your `PATH`, or replace `bin/cryptominisat5`.

## Testcase format

Each file under `data/testcases/` has two lines of **64 binary digits** (no spaces):

1. Plaintext  
2. Ciphertext  

Bit index `0` is the **leftmost** character (same indexing as the CNF generator).

## Full workflow

All commands assume the **repository root** as the working directory.

### 1. Make a testcase (optional)

```bash
python3 scripts/make_testcase.py <rounds> <key> [plaintext] -o data/testcases/my.txt
```

`key` / `plaintext` may be an 80-/64-bit `0`/`1` string or `0x` hex (`k0` / bit0 = LSB of the integer).

### 2. Generate CNF

```bash
python3 scripts/gen_present_cnf.py <rounds> <testcase_path>
```

Example:

```bash
python3 scripts/gen_present_cnf.py 2 data/testcases/testcase1.txt
# → out/cnf/present_r2_testcase1_keysched.cnf
# Unknowns: 80 master-key bits (variables 1 … 80)
```

### 3. Solve

```bash
./bin/cryptominisat5 out/cnf/present_r2_testcase1_keysched.cnf \
  > out/solutions/solution_r2_testcase1.txt
```

### 4. Extract the key

```bash
python3 scripts/extract_key.py out/solutions/solution_r2_testcase1.txt
python3 scripts/extract_key.py out/solutions/solution_r2_testcase1.txt --hex
# or: grep/pipe from stdin
./bin/cryptominisat5 out/cnf/present_r2_testcase1_keysched.cnf \
  | python3 scripts/extract_key.py -
```

Variables `1..80`: positive literal → `1`, negative → `0`.

### 5. Verify

```bash
python3 scripts/verify_solution.py 2 data/testcases/testcase1.txt \
  out/solutions/solution_r2_testcase1.txt
```

Verification uses the **same semantics** as `gen_present_cnf.py` (`R` rounds of ARK→S→P, then final ARK with `key_registers[R]`).

### Demo (1-round, already solved)

```bash
python3 scripts/gen_present_cnf.py 1 data/testcases/testcase1.txt
./bin/cryptominisat5 out/cnf/present_r1_testcase1_keysched.cnf \
  > out/solutions/solution_r1_testcase1_demo.txt
python3 scripts/verify_solution.py 1 data/testcases/testcase1.txt \
  out/solutions/solution_r1_testcase1_demo.txt
```

## Tests & CI

```bash
make test                 # creates .venv, unit + SAT (Linux) tests
./scripts/run_tests.sh    # same idea
make test-unit            # no solver required
make present-tv           # PRESENT paper 31-round test vectors
```

GitHub Actions (`.github/workflows/ci.yml`):

- All PRs/pushes: unit tests (no binary required for the unit job).
- Linux job: also runs small-round SAT tests (rounds 1–2) with `bin/cryptominisat5`.

## Benchmarks

```bash
python3 scripts/benchmark.py --rounds 1,2,3,4,5 --maxtime 30
python3 scripts/benchmark.py --rounds 1,2,3,4,5 --maxtime 30 --extra-rounds 8,16,31
# → results/benchmarks.csv + results/README.md
```

Do **not** commit huge CNF files; they stay under gitignored `out/`.

## Experiment report

Write-up covering threat model, encoding, scaling, small-round success, why 31-round SAT key recovery is intractable in practice, reproduction, and relation to `archive/v1`:

→ **[docs/experiment-report.md](docs/experiment-report.md)**

## Notes

- Real PRESENT-80 uses **31** rounds. Use small \(R\) to validate the encoding; larger instances grow in difficulty far faster than in file size.
- `scripts/present80.py` provides both CNF-aligned `encrypt()` and paper-accurate `encrypt_spec()` (for official test vectors).
- `archive/gen_present_cnf_v1.py` does not model the key schedule: each round key is an independent unknown.

## License

- Project scripts, testcases, and docs: [MIT](LICENSE) © JayWu1110  
- Bundled CryptoMiniSat binary/libs (`bin/`, `lib/`): MIT, redistributed from [msoos/cryptominisat](https://github.com/msoos/cryptominisat) — see [THIRD_PARTY.md](THIRD_PARTY.md)

The ~5MB static `bin/cryptominisat5` is **included in this repo** so Linux amd64 users can clone and run without a separate install. Other platforms should use Option B above.
