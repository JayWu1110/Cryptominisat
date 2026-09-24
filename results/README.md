# Benchmark results

Generated: **2026-09-23 13:29 UTC**

Hardware / environment: Linux 6.6.87.1-microsoft-standard-WSL2 (x86_64); CPU: 13th Gen Intel(R) Core(TM) i7-13620H

Solver: bundled `bin/cryptominisat5` (CryptoMiniSat 5.x).
CNF files are regenerated under `out/cnf/` (gitignored).

| Rounds | Vars | Clauses | Result | Wall time (s) | Max time (s) | Testcase |
|-------:|-----:|--------:|:-------|--------------:|-------------:|:---------|
| 1 | 724 | 2496 | SAT | 0.004 | 30.0 | `data/testcases/testcase1.txt` |
| 2 | 1160 | 4448 | SAT | 0.115 | 30.0 | `data/testcases/testcase1.txt` |
| 3 | 1596 | 6400 | TIMEOUT | 29.204 | 30.0 | `data/testcases/testcase1.txt` |
| 4 | 2032 | 8352 | TIMEOUT | 29.311 | 30.0 | `data/testcases/testcase1.txt` |
| 5 | 2468 | 10304 | TIMEOUT | 29.201 | 30.0 | `data/testcases/testcase1.txt` |
| 31 | 13804 | 61056 | TIMEOUT | 29.210 | 30.0 | `data/testcases/testcase1.txt` |

Raw data: [`benchmarks.csv`](benchmarks.csv).

Notes:

- Small round counts (1–5) are for encoding validation; real PRESENT-80 uses 31 rounds.
- `TIMEOUT` means the solver hit `--maxtime` without a decisive answer — expected for larger instances.
- Do not commit huge CNF or solution dumps; keep regenerating into `out/`.
