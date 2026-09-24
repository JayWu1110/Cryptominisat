#!/usr/bin/env python3
"""Extract the 80-bit PRESENT master key from a CryptoMiniSat solution.

SAT variables 1..80 are the master key (positive literal -> 1, negative -> 0).
Reads a solution file or stdin; prints the 80-bit string (and hex with k0=LSB).
"""

from __future__ import annotations

import argparse
import sys
from typing import Dict, Iterable, Optional, TextIO


def parse_assignment(lines: Iterable[str]) -> Dict[int, int]:
    """Parse s/v lines into var_index -> 0|1. Raises if UNSAT or incomplete key."""
    status: Optional[str] = None
    vals: Dict[int, int] = {}

    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        if line.startswith("s "):
            status = line[2:].strip()
            continue
        if line.startswith("c ") or line.startswith("c\t"):
            continue
        # CryptoMiniSat uses "v " lines; allow bare "v" with following tokens
        if line == "v" or line.startswith("v ") or (line[0] in "+-" and line[1:].split()[0].lstrip("+-").isdigit()):
            tokens = line.split()
            if tokens and tokens[0] == "v":
                tokens = tokens[1:]
            for tok in tokens:
                if tok == "0":
                    continue
                try:
                    lit = int(tok)
                except ValueError:
                    continue
                if lit == 0:
                    continue
                vals[abs(lit)] = 1 if lit > 0 else 0

    if status is None:
        # Some solvers omit "s" but still emit "v"; treat as OK if we have key bits
        if not any(i in vals for i in range(1, 81)):
            raise ValueError("no solution status and no key variables found")
    elif status.upper() != "SATISFIABLE":
        raise ValueError(f"solver status is {status!r}, expected SATISFIABLE")

    missing = [i for i in range(1, 81) if i not in vals]
    if missing:
        raise ValueError(f"missing assignment for key variables: {missing[:10]}...")

    return vals


def key_bits_from_assignment(vals: Dict[int, int]) -> str:
    return "".join(str(vals[i]) for i in range(1, 81))


def key_hex_from_bits(bitstr: str) -> str:
    """Hex with bit index 0 (k_0) as LSB of the integer."""
    v = 0
    for i, c in enumerate(bitstr):
        if c == "1":
            v |= 1 << i
    return f"{v:020x}"


def extract_from_file(f: TextIO) -> str:
    vals = parse_assignment(f)
    return key_bits_from_assignment(vals)


def main(argv: Optional[list] = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "solution",
        nargs="?",
        default="-",
        help="solution file path, or '-' for stdin (default)",
    )
    p.add_argument(
        "--hex",
        action="store_true",
        help="also print hex (k_0 = LSB)",
    )
    args = p.parse_args(argv)

    try:
        if args.solution == "-":
            key = extract_from_file(sys.stdin)
        else:
            with open(args.solution, "r", encoding="utf-8", errors="replace") as f:
                key = extract_from_file(f)
    except (ValueError, OSError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    print(key)
    if args.hex:
        print(key_hex_from_bits(key))
    return 0


if __name__ == "__main__":
    sys.exit(main())
