#!/usr/bin/env python3
"""Benchmark PRESENT CNF generation + CryptoMiniSat solve times.

Writes results/benchmarks.csv and regenerates the markdown table in
results/README.md.
"""

from __future__ import annotations

import argparse
import csv
import os
import platform
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
BIN = ROOT / "bin" / "cryptominisat5"
DEFAULT_ROUNDS = [1, 2, 3, 4, 5]


def parse_cnf_header(path: Path) -> Tuple[int, int]:
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("p cnf"):
                parts = line.split()
                return int(parts[2]), int(parts[3])
    raise ValueError(f"no DIMACS header in {path}")


def classify_result(text: str, timed_out: bool) -> str:
    if timed_out:
        return "TIMEOUT"
    if re.search(r"^s SATISFIABLE", text, re.M):
        return "SAT"
    if re.search(r"^s UNSATISFIABLE", text, re.M):
        return "UNSAT"
    return "UNKNOWN"


def run_one(
    rounds: int,
    testcase: Path,
    maxtime: float,
    solver: Path,
) -> dict:
    cnf_dir = ROOT / "out" / "cnf"
    sol_dir = ROOT / "out" / "solutions"
    cnf_dir.mkdir(parents=True, exist_ok=True)
    sol_dir.mkdir(parents=True, exist_ok=True)

    base = testcase.stem
    cnf_path = cnf_dir / f"present_r{rounds}_{base}_keysched.cnf"
    sol_path = sol_dir / f"bench_r{rounds}_{base}.txt"

    gen = subprocess.run(
        [sys.executable, str(SCRIPTS / "gen_present_cnf.py"), str(rounds), str(testcase)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    if gen.returncode != 0:
        return {
            "rounds": rounds,
            "vars": "",
            "clauses": "",
            "result": "GEN_FAIL",
            "wall_time_s": "",
            "solution_path": "",
            "maxtime_s": maxtime,
            "testcase": str(testcase.relative_to(ROOT)),
        }

    nvars, nclauses = parse_cnf_header(cnf_path)

    timed_out = False
    t0 = time.perf_counter()
    try:
        with open(sol_path, "w", encoding="utf-8") as outf:
            proc = subprocess.run(
                [str(solver), f"--maxtime={maxtime}", str(cnf_path)],
                stdout=outf,
                stderr=subprocess.DEVNULL,
                cwd=str(ROOT),
                timeout=maxtime + 30,
                check=False,
            )
        # CMS may kill itself on maxtime; also detect via output
    except subprocess.TimeoutExpired:
        timed_out = True
        with open(sol_path, "a", encoding="utf-8") as outf:
            outf.write("\nc benchmark wrapper: process TimeoutExpired\n")
    wall = time.perf_counter() - t0

    text = sol_path.read_text(encoding="utf-8", errors="replace") if sol_path.is_file() else ""
    # CryptoMiniSat prints "c time out reached" or exits without s-line on timeout
    if "time out" in text.lower() or "timeout" in text.lower():
        if "s SATISFIABLE" not in text and "s UNSATISFIABLE" not in text:
            timed_out = True
    result = classify_result(text, timed_out)
    if result == "UNKNOWN" and wall >= maxtime * 0.95:
        result = "TIMEOUT"

    try:
        rel_sol = str(sol_path.relative_to(ROOT))
    except ValueError:
        rel_sol = str(sol_path)

    return {
        "rounds": rounds,
        "vars": nvars,
        "clauses": nclauses,
        "result": result,
        "wall_time_s": f"{wall:.3f}",
        "solution_path": rel_sol,
        "maxtime_s": maxtime,
        "testcase": str(testcase.relative_to(ROOT)),
    }


def write_csv(rows: List[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "rounds",
        "vars",
        "clauses",
        "result",
        "wall_time_s",
        "maxtime_s",
        "testcase",
        "solution_path",
    ]
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k, "") for k in fields})


def write_readme(rows: List[dict], path: Path, hardware_note: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "# Benchmark results",
        "",
        f"Generated: **{now}**",
        "",
        f"Hardware / environment: {hardware_note}",
        "",
        "Solver: bundled `bin/cryptominisat5` (CryptoMiniSat 5.x).",
        "CNF files are regenerated under `out/cnf/` (gitignored).",
        "",
        "| Rounds | Vars | Clauses | Result | Wall time (s) | Max time (s) | Testcase |",
        "|-------:|-----:|--------:|:-------|--------------:|-------------:|:---------|",
    ]
    for r in rows:
        lines.append(
            f"| {r['rounds']} | {r['vars']} | {r['clauses']} | {r['result']} "
            f"| {r['wall_time_s']} | {r['maxtime_s']} | `{r['testcase']}` |"
        )
    lines.extend(
        [
            "",
            "Raw data: [`benchmarks.csv`](benchmarks.csv).",
            "",
            "Notes:",
            "",
            "- Small round counts (1–5) are for encoding validation; real PRESENT-80 uses 31 rounds.",
            "- `TIMEOUT` means the solver hit `--maxtime` without a decisive answer — expected for larger instances.",
            "- Do not commit huge CNF or solution dumps; keep regenerating into `out/`.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def default_hardware_note() -> str:
    uname = platform.uname()
    cpu = uname.processor or platform.machine()
    # Try /proc/cpuinfo model name on Linux
    model = ""
    try:
        with open("/proc/cpuinfo", encoding="utf-8", errors="replace") as f:
            for line in f:
                if line.startswith("model name"):
                    model = line.split(":", 1)[1].strip()
                    break
    except OSError:
        pass
    bits = f"{uname.system} {uname.release} ({uname.machine})"
    if model:
        return f"{bits}; CPU: {model}"
    return f"{bits}; processor={cpu}"


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--rounds",
        default=",".join(str(r) for r in DEFAULT_ROUNDS),
        help="comma-separated round counts (default: 1,2,3,4,5)",
    )
    p.add_argument(
        "--testcase",
        default=str(ROOT / "data" / "testcases" / "testcase1.txt"),
        help="testcase path",
    )
    p.add_argument(
        "--maxtime",
        type=float,
        default=30.0,
        help="solver time limit in seconds (default: 30)",
    )
    p.add_argument(
        "--extra-rounds",
        default="",
        help="optional extra rounds (e.g. 8,16,31) using the same --maxtime",
    )
    p.add_argument(
        "--solver",
        default=str(BIN),
        help="path to cryptominisat5",
    )
    args = p.parse_args(argv)

    solver = Path(args.solver)
    if not solver.is_file():
        print(f"Error: solver not found: {solver}", file=sys.stderr)
        return 1

    rounds: List[int] = [int(x) for x in args.rounds.split(",") if x.strip()]
    if args.extra_rounds.strip():
        rounds.extend(int(x) for x in args.extra_rounds.split(",") if x.strip())

    testcase = Path(args.testcase)
    if not testcase.is_file():
        print(f"Error: testcase not found: {testcase}", file=sys.stderr)
        return 1

    rows = []
    for r in rounds:
        print(f"=== rounds={r} maxtime={args.maxtime}s ===", file=sys.stderr)
        row = run_one(r, testcase, args.maxtime, solver)
        print(
            f"  -> {row['result']} vars={row['vars']} clauses={row['clauses']} "
            f"time={row['wall_time_s']}s",
            file=sys.stderr,
        )
        rows.append(row)

    csv_path = ROOT / "results" / "benchmarks.csv"
    md_path = ROOT / "results" / "README.md"
    write_csv(rows, csv_path)
    write_readme(rows, md_path, default_hardware_note())
    print(f"Wrote {csv_path}", file=sys.stderr)
    print(f"Wrote {md_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
