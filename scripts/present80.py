#!/usr/bin/env python3
"""Pure-Python PRESENT-80 reference matching scripts/gen_present_cnf.py semantics.

Bit indexing (same as the CNF model):
  - State: 64 bits, index 0 .. 63 (testcase string char i -> bit i)
  - Key register: 80 bits, index 0 .. 79 corresponding to k_0 .. k_79
  - Round key for AddRoundKey: key_register[16:80]  (k_16 .. k_79)
  - R rounds of ARK -> S -> P, then a final ARK with key_registers[R]
"""

from __future__ import annotations

from typing import List, Sequence

SBOX_TABLE = [
    0xC, 0x5, 0x6, 0xB, 0x9, 0x0, 0xA, 0xD,
    0x3, 0xE, 0xF, 0x8, 0x4, 0x7, 0x1, 0x2,
]

PLAYER_PERMUTATION = {}
for _i in range(63):
    PLAYER_PERMUTATION[_i] = (16 * _i) % 63
PLAYER_PERMUTATION[63] = 63


def bits_from_str(s: str) -> List[int]:
    if any(c not in "01" for c in s):
        raise ValueError(f"expected bitstring of 0/1, got {s!r}")
    return [int(c) for c in s]


def bits_to_str(bits: Sequence[int]) -> str:
    return "".join("1" if b else "0" for b in bits)


def bits_from_int(value: int, width: int) -> List[int]:
    """LSB of value -> index 0 (matches CNF / integer bit numbering)."""
    return [(value >> i) & 1 for i in range(width)]


def bits_to_int(bits: Sequence[int]) -> int:
    v = 0
    for i, b in enumerate(bits):
        if b:
            v |= 1 << i
    return v


def sbox_nibble(bits4: Sequence[int]) -> List[int]:
    """4 bits with bits4[0]=MSB (x3), bits4[3]=LSB (x0) — same as CNF S-box."""
    if len(bits4) != 4:
        raise ValueError("nibble must be 4 bits")
    x = 0
    for i in range(4):
        # bits4[3-i] is bit i of the nibble value
        if bits4[3 - i]:
            x |= 1 << i
    y = SBOX_TABLE[x]
    out = [0, 0, 0, 0]
    for i in range(4):
        out[3 - i] = (y >> i) & 1
    return out


def sbox_layer(state: Sequence[int]) -> List[int]:
    """CNF data-path S-box: each group state[4i:4i+4] has index 0 as nibble MSB.

    Note: the PRESENT specification uses the opposite nibble packing
    (MSB = s_{4i+3}). Use sbox_layer_spec() for paper-accurate encryption.
    """
    if len(state) != 64:
        raise ValueError("state must be 64 bits")
    out: List[int] = []
    for i in range(16):
        out.extend(sbox_nibble(state[i * 4 : (i + 1) * 4]))
    return out


def sbox_layer_spec(state: Sequence[int]) -> List[int]:
    """PRESENT-paper data-path S-box: w_i = s_{4i+3}||s_{4i+2}||s_{4i+1}||s_{4i}."""
    if len(state) != 64:
        raise ValueError("state must be 64 bits")
    out = [0] * 64
    for i in range(16):
        # MSB..LSB = s_{4i+3} .. s_{4i}
        y = sbox_nibble(
            [state[4 * i + 3], state[4 * i + 2], state[4 * i + 1], state[4 * i]]
        )
        out[4 * i + 3], out[4 * i + 2], out[4 * i + 1], out[4 * i] = y
    return out


def player(state: Sequence[int]) -> List[int]:
    if len(state) != 64:
        raise ValueError("state must be 64 bits")
    out = [0] * 64
    for i in range(64):
        out[PLAYER_PERMUTATION[i]] = state[i]
    return out


def add_round_key(state: Sequence[int], key_reg: Sequence[int]) -> List[int]:
    """XOR state with key_reg[16:80] (k_16 .. k_79)."""
    rk = key_reg[16:80]
    if len(state) != 64 or len(rk) != 64:
        raise ValueError("state/round-key must be 64 bits")
    return [s ^ k for s, k in zip(state, rk)]


def key_schedule_update(key_reg: Sequence[int], round_counter: int) -> List[int]:
    """One PRESENT-80 key-register update (round_counter is 1-based)."""
    if len(key_reg) != 80:
        raise ValueError("key register must be 80 bits")
    if round_counter < 1:
        raise ValueError("round_counter must be >= 1")

    # 61-bit left rotation: new[j] = old[(j - 61) % 80]
    rotated = [key_reg[(j - 61) % 80] for j in range(80)]

    # S-box on 4 MSBs k_79..k_76 (matches both CNF and the PRESENT paper)
    sboxed = list(rotated)
    sboxed[79], sboxed[78], sboxed[77], sboxed[76] = sbox_nibble(
        [rotated[79], rotated[78], rotated[77], rotated[76]]
    )

    # XOR round counter into k_19..k_15
    rc = round_counter
    rc_bits = [(rc >> bit) & 1 for bit in range(4, -1, -1)]  # MSB..LSB
    next_reg = list(sboxed)
    for j in range(15, 20):
        rc_bit_val = rc_bits[4 - (j - 15)]
        next_reg[j] = sboxed[j] ^ rc_bit_val
    return next_reg


def generate_round_keys(master_key: Sequence[int], rounds: int) -> List[List[int]]:
    """Return key_registers[0..rounds] (length rounds+1), matching the CNF."""
    if len(master_key) != 80:
        raise ValueError("master key must be 80 bits")
    regs = [list(master_key)]
    for i in range(1, rounds + 1):
        regs.append(key_schedule_update(regs[-1], i))
    return regs


def _encrypt_with_sbox(
    plaintext: Sequence[int],
    master_key: Sequence[int],
    rounds: int,
    sbox_fn,
) -> List[int]:
    if len(plaintext) != 64:
        raise ValueError("plaintext must be 64 bits")
    if rounds < 1:
        raise ValueError("rounds must be >= 1")

    key_regs = generate_round_keys(master_key, rounds)
    state = list(plaintext)
    for r in range(rounds):
        state = add_round_key(state, key_regs[r])
        state = sbox_fn(state)
        state = player(state)
    state = add_round_key(state, key_regs[rounds])
    return state


def encrypt(plaintext: Sequence[int], master_key: Sequence[int], rounds: int) -> List[int]:
    """Encrypt matching gen_present_cnf.py (CNF data-path S-box wiring)."""
    return _encrypt_with_sbox(plaintext, master_key, rounds, sbox_layer)


def encrypt_spec(
    plaintext: Sequence[int], master_key: Sequence[int], rounds: int = 31
) -> List[int]:
    """Encrypt matching the PRESENT specification (paper S-box nibble packing)."""
    return _encrypt_with_sbox(plaintext, master_key, rounds, sbox_layer_spec)


def encrypt_str(pt_bits: str, key_bits: str, rounds: int) -> str:
    return bits_to_str(encrypt(bits_from_str(pt_bits), bits_from_str(key_bits), rounds))


# --- Standard PRESENT-80 test vectors (31 rounds) from the PRESENT paper ---
# Values are integers; bit i of the integer is state/key bit i (index i).

PRESENT80_TV = [
    # (plaintext, key, ciphertext) as integers
    (0x0000000000000000, 0x00000000000000000000, 0x5579C1387B228445),
    (0x0000000000000000, 0xFFFFFFFFFFFFFFFFFFFF, 0xE72C46C0F5945049),
    (0xFFFFFFFFFFFFFFFF, 0x00000000000000000000, 0xA112FFC72F68417B),
    (0xFFFFFFFFFFFFFFFF, 0xFFFFFFFFFFFFFFFFFFFF, 0x3333DCD3213210D2),
]


def encrypt_hex(pt_hex: int, key_hex: int, rounds: int = 31) -> int:
    """Paper-accurate encrypt; for CNF semantics use encrypt() + bits_to_int."""
    pt = bits_from_int(pt_hex, 64)
    key = bits_from_int(key_hex, 80)
    return bits_to_int(encrypt_spec(pt, key, rounds))


if __name__ == "__main__":
    import sys

    ok = True
    for pt, key, ct in PRESENT80_TV:
        got = encrypt_hex(pt, key, 31)
        if got != ct:
            print(
                f"FAIL pt={pt:016X} key={key:020X}: got {got:016X} want {ct:016X}",
                file=sys.stderr,
            )
            ok = False
        else:
            print(f"OK   pt={pt:016X} key={key:020X} -> {ct:016X}")
    sys.exit(0 if ok else 1)
