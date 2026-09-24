# PRESENT-80 Algebraic Cryptanalysis Experiment Report

This workspace encodes truncated PRESENT-80 (encryption + key schedule) as CNF and recovers the 80-bit master key with CryptoMiniSat under a known-plaintext threat model. Rounds 1–2 solve quickly; from about 3 rounds upward the SAT search becomes expensive on commodity hardware within short time limits. Full **31-round** key recovery via plain SAT is **not** expected to finish in practice — our 30s attempt on the 31-round instance (13 804 vars / 61 056 clauses) timed out.

---

## 1. Threat model

| Item | Description |
|------|-------------|
| Attack type | **Known-plaintext** |
| Attacker knows | One 64-bit plaintext / ciphertext pair; round count \(R\) (may be truncated in experiments) |
| Attacker does not know | The 80-bit PRESENT-80 **master key** |
| Goal | Find a master key consistent with the key schedule such that \(\mathrm{Enc}_R(PT,K)=CT\) |
| Out of scope | Side channels, fault injection, distinguishing attacks with many PT/CT pairs, breaking live systems |

This experiment is **educational / validation-oriented algebraic cryptanalysis**: it shows that the “encode cipher + key schedule as SAT” pipeline works, and quantifies how solving difficulty grows with the round count — **not** a claim that full 31-round PRESENT can be broken in practice.

## 2. Encoding

Generator: `scripts/gen_present_cnf.py`.

- **Master key**: SAT variables `1..80` (the only unknown key bits).
- **Key schedule**: maintain `key_registers[0..R]`; each update is a 61-bit left rotate → S-box on \(k_{79..76}\) → XOR the round counter into \(k_{19..15}\).
- **Encryption path**: \(R\) rounds of **AddRoundKey → S-box → P-layer**, then a **final** AddRoundKey with `key_registers[R]` (a truncated structure consistent with PRESENT).
- **Round keys**: take \(k_{16..79}\) (64 bits) from the register and XOR bit-wise with the state.
- **Unit clauses**: fix the plaintext and ciphertext bits.

Reference implementation and verification: `encrypt()` in `scripts/present80.py` is **intentionally aligned with CNF semantics** (data-path S-box nibble bit order is reversed relative to the paper; the key-schedule S-box matches the paper). For official paper test vectors, use `encrypt_spec()` / `python3 scripts/present80.py`.

Legacy `archive/gen_present_cnf_v1.py`: **no** key schedule; each round key is an independent unknown — more variables and different semantics; kept only for historical comparison.

## 3. Variable / clause scale

Measured on testcase1 (approximately linear):

| \(R\) | Vars | Clauses | Approx. growth |
|------:|-----:|--------:|:---------------|
| 1 | 724 | 2496 | — |
| 2 | 1160 | 4448 | +436 vars / +1952 clauses |
| 5 | 2468 | 10304 | |
| 16 | 7264 | 31776 | |
| **31** | **13804** | **61056** | CNF ≈ **1.4 MB** |

Empirical formulas (this generator): \(\mathrm{vars} \approx 724 + 436(R-1)\), \(\mathrm{clauses} \approx 2496 + 1952(R-1)\).

The instance size itself is not large for modern SAT solvers; **the difficulty comes from search structure after cryptographic diffusion**, not from “the file is too big.”

## 4. Small-round success and benchmarks

Hardware (this run): WSL2, Intel Core i7-13620H, CryptoMiniSat 5.13.0 (`bin/cryptominisat5`), `--maxtime=30`.

See [`results/README.md`](../results/README.md) and [`results/benchmarks.csv`](../results/benchmarks.csv):

| Rounds | Result (30s) | Wall (s) |
|-------:|:-------------|---------:|
| 1 | **SAT** | 0.004 |
| 2 | **SAT** | 0.114 |
| 3–5, 8, 16, **31** | **TIMEOUT** | ≈29–30 |

Note: earlier artifacts left in the repo (`out/solutions/solution_r3_testcase1.txt`, `solution_r4_testcase1.txt`) pass `verify_solution.py` (so satisfying assignments were found under **longer time or different conditions**). Under a fixed 30-second budget, this machine often reports TIMEOUT from \(R=3\) onward — the two observations are not contradictory; only the time limit differs.

Automated tests (`tests/`) cover: S-box / P-layer, paper 31-round test vectors (`encrypt_spec`), `extract_key` parsing, and **1–2 round** gen→solve→extract→verify end-to-end.

## 5. Why full 31-round “plain SAT key recovery” is impractical

1. **Search space**: nominally still an 80-bit key, but with few truncated rounds the constraints are weak and heuristics often hit a solution; near full PRESENT, stacked nonlinear layers make CDCL pruning ineffective.
2. **Single known-plaintext pair**: information-theoretically the ciphertext gives only 64 bits while the key is 80 bits, so solutions are not unique; in practice the solver must still search a huge residual space for *any* consistent assignment.
3. **Experimental evidence**: the 31-round CNF is only ~1.4 MB / ~13k variables, yet **no result within 30 seconds**; it is reasonable **not** to expect a stable recovery of the full 31-round master key on a typical laptop/workstation within acceptable time (minutes to a few hours).
4. **Relation to real cryptanalysis**: published PRESENT attacks use differential / linear / meet-in-the-middle structure; “SAT the whole cipher” is usually only useful as an encoding-correctness check, not as a practical break of full round counts.

**Honest conclusion:** this project demonstrates the pipeline and small-round feasibility; **full 31-round PRESENT-80 plaintext SAT key recovery is not expected to complete.**

## 6. How to reproduce

```bash
# Unit tests + (Linux) small-round SAT
make test
# or
./scripts/run_tests.sh

# Custom testcase → CNF → solve → extract key → verify
python3 scripts/make_testcase.py 2 0x0123...your80bitkey 0x0123456789abcdef \
  -o data/testcases/my.txt
python3 scripts/gen_present_cnf.py 2 data/testcases/my.txt
./bin/cryptominisat5 out/cnf/present_r2_my_keysched.cnf \
  > out/solutions/sol_r2_my.txt
python3 scripts/extract_key.py out/solutions/sol_r2_my.txt --hex
python3 scripts/verify_solution.py 2 data/testcases/my.txt out/solutions/sol_r2_my.txt

# Benchmarks (writes results/)
python3 scripts/benchmark.py --rounds 1,2,3,4,5 --maxtime 30 --extra-rounds 31
```

Generate the 31-round CNF and try briefly:

```bash
python3 scripts/gen_present_cnf.py 31 data/testcases/testcase1.txt
./bin/cryptominisat5 --maxtime=30 out/cnf/present_r31_testcase1_keysched.cnf \
  > out/solutions/bench_r31_testcase1.txt
# Expected: no s SATISFIABLE (TIMEOUT / INDETERMINATE)
```

## 7. Limitations and caveats

- Data-path S-box nibble endianness does not fully match the PRESENT paper; verification must use CNF-aligned `present80.encrypt` — do not use paper vectors directly as CNF testcases.
- Single PT/CT pair; no multi-pair modeling, uniqueness proof for the correct key, or UNSAT cores.
- Bundled solver is a Linux amd64 static binary; other platforms must supply their own CryptoMiniSat.
- Large CNF / solution files are gitignored by default; do not commit huge solution dumps.
- The `archive/` legacy generator has different semantics; do not mix results with the current keysched CNF.

## 8. Relation to archive/v1

| | `scripts/gen_present_cnf.py` (current) | `archive/gen_present_cnf_v1.py` |
|--|--|--|
| Key schedule | Yes (PRESENT-80) | No |
| Unknown key bits | Fixed 80 bit | Independent per round; grows with \(R\) |
| Role | This report and toolchain | Historical / comparison |

---

*This report matches the repo toolchain: reference cipher, key extraction, verification, pytest, CI, and benchmark. Experimental numbers live under `results/` and can be regenerated at any time.*
