#!/usr/bin/env python3
"""Generate a PRESENT-80 testcase (PT + CT bitstrings) from a known key."""

from __future__ import annotations

import argparse
import os
import sys

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

from present80 import bits_from_str, bits_to_str, encrypt  # noqa: E402


def parse_bits(s: str, width: int, name: str) -> str:
    s = s.strip().lower()
    if s.startswith("0x"):
        v = int(s, 16)
        bits = [(v >> i) & 1 for i in range(width)]
        return "".join(str(b) for b in bits)
    if all(c in "01" for c in s) and len(s) == width:
        return s
    raise ValueError(
        f"{name} must be a {width}-bit 0/1 string or 0x-hex (got len={len(s)})"
    )


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("rounds", type=int, help="number of rounds (ARK->S->P) + final ARK")
    p.add_argument("key", help="80-bit master key as bitstring or 0x hex (k0=LSB)")
    p.add_argument(
        "plaintext",
        nargs="?",
        default="0" * 64,
        help="64-bit plaintext bitstring or 0x hex (default: all-zero)",
    )
    p.add_argument(
        "-o",
        "--output",
        help="write testcase file (default: stdout)",
    )
    args = p.parse_args(argv)

    if args.rounds < 1:
        print("Error: rounds must be >= 1", file=sys.stderr)
        return 1

    try:
        key = parse_bits(args.key, 80, "key")
        pt = parse_bits(args.plaintext, 64, "plaintext")
        ct = bits_to_str(encrypt(bits_from_str(pt), bits_from_str(key), args.rounds))
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    body = f"{pt}\n{ct}\n"
    if args.output:
        os.makedirs(os.path.dirname(os.path.abspath(args.output)) or ".", exist_ok=True)
        with open(args.output, "w", encoding="utf-8", newline="\n") as f:
            f.write(body)
        print(f"Wrote {args.output}", file=sys.stderr)
    else:
        sys.stdout.write(body)
    return 0


if __name__ == "__main__":
    sys.exit(main())
