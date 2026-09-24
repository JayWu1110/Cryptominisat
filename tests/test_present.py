#!/usr/bin/env python3
"""Unit and integration tests for PRESENT-80 CNF tooling."""

from __future__ import annotations

import os
import platform
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
BIN = ROOT / "bin" / "cryptominisat5"
sys.path.insert(0, str(SCRIPTS))

from extract_key import (  # noqa: E402
    extract_from_file,
    key_bits_from_assignment,
    key_hex_from_bits,
    parse_assignment,
)
from present80 import (  # noqa: E402
    PLAYER_PERMUTATION,
    PRESENT80_TV,
    SBOX_TABLE,
    bits_from_int,
    bits_from_str,
    bits_to_str,
    encrypt,
    encrypt_hex,
    encrypt_spec,
    player,
    sbox_nibble,
)


def _solver_available() -> bool:
    if platform.system() != "Linux":
        return False
    if not BIN.is_file():
        return False
    return os.access(BIN, os.X_OK)


needs_solver = pytest.mark.skipif(
    not _solver_available(),
    reason="Linux cryptominisat5 binary not available",
)


class TestSboxPlayer:
    def test_sbox_table_length(self):
        assert len(SBOX_TABLE) == 16
        assert sorted(SBOX_TABLE) == list(range(16))

    def test_sbox_known_values(self):
        # PRESENT S-box: 0->C, 1->5, ..., F->2
        assert SBOX_TABLE[0x0] == 0xC
        assert SBOX_TABLE[0x1] == 0x5
        assert SBOX_TABLE[0xF] == 0x2
        assert sbox_nibble([0, 0, 0, 0]) == [1, 1, 0, 0]  # 0 -> C
        assert sbox_nibble([1, 1, 1, 1]) == [0, 0, 1, 0]  # F -> 2

    def test_player_fixed_points_and_formula(self):
        assert PLAYER_PERMUTATION[63] == 63
        for i in range(63):
            assert PLAYER_PERMUTATION[i] == (16 * i) % 63
        # Identity on a single 1 at position 0 -> position 0
        state = [0] * 64
        state[0] = 1
        out = player(state)
        assert out[0] == 1
        assert sum(out) == 1
        # Position 1 -> 16
        state = [0] * 64
        state[1] = 1
        assert player(state)[16] == 1


class TestPresentSpecVectors:
    def test_full_31_round_paper_vectors(self):
        for pt, key, ct in PRESENT80_TV:
            assert encrypt_hex(pt, key, 31) == ct

    def test_spec_vs_cnf_differ_nonzero(self):
        # Data-path nibble packing differs; all-zero still collides for 1 round
        # but a patterned input should diverge for CNF vs paper S-box wiring.
        pt = bits_from_int(0x0123456789ABCDEF, 64)
        key = bits_from_int(0x0F1E2D3C4B5A69788796, 80)
        cnf_ct = bits_to_str(encrypt(pt, key, 3))
        spec_ct = bits_to_str(encrypt_spec(pt, key, 3))
        assert cnf_ct != spec_ct


class TestExtractKey:
    def test_parse_basic(self):
        lines = [
            "c comment\n",
            "s SATISFIABLE\n",
            "v -1 2 -3 4 0\n",
            "v " + " ".join(str(i) for i in range(5, 81)) + " 0\n",
        ]
        vals = parse_assignment(lines)
        bits = key_bits_from_assignment(vals)
        assert bits[:4] == "0101"
        assert len(bits) == 80
        hx = key_hex_from_bits(bits)
        assert len(hx) == 20
        # k0=0, k1=1, k2=0, k3=1 → low nibble bits ... reconstructible
        assert int(hx, 16) & 0xF == 0xA  # bits 0..3 = 0101 binary = 0xA with k0=LSB

    def test_unsat_raises(self):
        with pytest.raises(ValueError, match="UNSAT"):
            parse_assignment(["s UNSATISFIABLE\n"])

    def test_extract_from_demo_file(self):
        demo = ROOT / "out" / "solutions" / "solution_r1_testcase1_demo.txt"
        if not demo.is_file():
            pytest.skip("demo solution not present")
        with open(demo, encoding="utf-8", errors="replace") as f:
            key = extract_from_file(f)
        assert len(key) == 80
        assert set(key) <= {"0", "1"}


class TestMakeTestcaseRoundtrip:
    def test_encrypt_matches_make_testcase(self, tmp_path: Path):
        key = "1" + "0" * 79
        pt = "01" * 32
        ct = bits_to_str(encrypt(bits_from_str(pt), bits_from_str(key), 2))
        out = tmp_path / "tc.txt"
        subprocess.check_call(
            [
                sys.executable,
                str(SCRIPTS / "make_testcase.py"),
                "2",
                key,
                pt,
                "-o",
                str(out),
            ],
            cwd=str(ROOT),
        )
        lines = out.read_text(encoding="utf-8").splitlines()
        assert lines[0] == pt
        assert lines[1] == ct


@needs_solver
class TestSatSolveSmallRounds:
    @pytest.mark.parametrize("rounds", [1, 2])
    def test_gen_solve_extract_verify(self, rounds: int, tmp_path: Path):
        # Deterministic easy instance (all-zero key/PT under CNF semantics).
        key = "0" * 80
        pt = "0" * 64
        tc = tmp_path / "tc.txt"
        subprocess.check_call(
            [
                sys.executable,
                str(SCRIPTS / "make_testcase.py"),
                str(rounds),
                key,
                pt,
                "-o",
                str(tc),
            ],
            cwd=str(ROOT),
        )

        env_out = ROOT / "out" / "cnf"
        env_out.mkdir(parents=True, exist_ok=True)
        subprocess.check_call(
            [
                sys.executable,
                str(SCRIPTS / "gen_present_cnf.py"),
                str(rounds),
                str(tc),
            ],
            cwd=str(ROOT),
        )
        cnf = env_out / f"present_r{rounds}_{tc.stem}_keysched.cnf"
        assert cnf.is_file()

        sol = tmp_path / "sol.txt"
        timeout = 30
        with open(sol, "w", encoding="utf-8") as outf:
            proc = subprocess.run(
                [str(BIN), f"--maxtime={timeout}", str(cnf)],
                stdout=outf,
                stderr=subprocess.DEVNULL,
                cwd=str(ROOT),
                timeout=timeout + 30,
                check=False,
            )
        text = sol.read_text(encoding="utf-8", errors="replace")
        assert "s SATISFIABLE" in text, f"exit={proc.returncode}\n{text[-500:]}"

        with open(sol, encoding="utf-8", errors="replace") as f:
            recovered = extract_from_file(f)
        got = bits_to_str(
            encrypt(bits_from_str(pt), bits_from_str(recovered), rounds)
        )
        exp = bits_to_str(encrypt(bits_from_str(pt), bits_from_str(key), rounds))
        assert got == exp

        subprocess.check_call(
            [
                sys.executable,
                str(SCRIPTS / "verify_solution.py"),
                str(rounds),
                str(tc),
                str(sol),
            ],
            cwd=str(ROOT),
        )

    def test_demo_solution_verifies(self):
        demo = ROOT / "out" / "solutions" / "solution_r1_testcase1_demo.txt"
        tc = ROOT / "data" / "testcases" / "testcase1.txt"
        if not demo.is_file():
            pytest.skip("demo solution not present")
        subprocess.check_call(
            [
                sys.executable,
                str(SCRIPTS / "verify_solution.py"),
                "1",
                str(tc),
                str(demo),
            ],
            cwd=str(ROOT),
        )


def test_extract_key_cli_stdin():
    sample = "s SATISFIABLE\nv " + " ".join(
        str(i if i % 2 else -i) for i in range(1, 81)
    ) + " 0\n"
    proc = subprocess.run(
        [sys.executable, str(SCRIPTS / "extract_key.py"), "-"],
        input=sample,
        text=True,
        capture_output=True,
        cwd=str(ROOT),
        check=False,
    )
    assert proc.returncode == 0
    assert proc.stdout.strip() == "".join("1" if i % 2 else "0" for i in range(1, 81))
