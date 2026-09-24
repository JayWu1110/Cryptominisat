#!/usr/bin/env python3
"""Verify a CryptoMiniSat solution against a PRESENT testcase.

Extracts the 80-bit master key and checks that encrypt(PT, key, rounds)
matches the ciphertext, using the same semantics as gen_present_cnf.py
(R rounds of ARK->S->P then final ARK with key_registers[R]).
"""

from __future__ import annotations

import argparse
import os
import sys

# Allow running as script from repo root or scripts/
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

from extract_key import extract_from_file  # noqa: E402
from present80 import bits_from_str, bits_to_str, encrypt  # noqa: E402


def read_testcase(path: str):
    with open(path, "r", encoding="utf-8") as f:
        pt = f.readline().strip()
        ct = f.readline().strip()
    if len(pt) != 64 or len(ct) != 64:
        raise ValueError(f"testcase must have two 64-bit lines (got {len(pt)}, {len(ct)})")
    if any(c not in "01" for c in pt + ct):
        raise ValueError("testcase lines must be binary digits")
    return pt, ct


def verify(rounds: int, testcase_path: str, solution_path: str) -> bool:
    pt_s, ct_s = read_testcase(testcase_path)
    with open(solution_path, "r", encoding="utf-8", errors="replace") as f:
        key_s = extract_from_file(f)

    got = bits_to_str(encrypt(bits_from_str(pt_s), bits_from_str(key_s), rounds))
    if got != ct_s:
        print("VERIFY FAIL", file=sys.stderr)
        print(f"  rounds   : {rounds}", file=sys.stderr)
        print(f"  key      : {key_s}", file=sys.stderr)
        print(f"  plaintext: {pt_s}", file=sys.stderr)
        print(f"  expected : {ct_s}", file=sys.stderr)
        print(f"  got      : {got}", file=sys.stderr)
        return False

    print("VERIFY OK")
    print(f"  rounds: {rounds}")
    print(f"  key   : {key_s}")
    return True


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("rounds", type=int, help="number of PRESENT rounds (same as CNF gen)")
    p.add_argument("testcase", help="path to testcase (PT then CT bitstrings)")
    p.add_argument("solution", help="CryptoMiniSat solution file")
    args = p.parse_args(argv)

    if args.rounds < 1:
        print("Error: rounds must be >= 1", file=sys.stderr)
        return 1
    try:
        ok = verify(args.rounds, args.testcase, args.solution)
    except (ValueError, OSError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
