#!/usr/bin/env python3

import sys
import os
from typing import List, Tuple

# --- Constants from PDF ---

# S-box look-up table
# Index X (0-15) maps to value Y (0-15)
#
SBOX_TABLE = [
    0xC, 0x5, 0x6, 0xB, 0x9, 0x0, 0xA, 0xD, 
    0x3, 0xE, 0xF, 0x8, 0x4, 0x7, 0x1, 0x2
]

# P-layer permutation table
#  "P(i)=(16i) mod 63"
#  "2*64=128 clauses" implies P(63) must be defined.
# We assume P(63) = 63.
PLAYER_PERMUTATION = {}
for i in range(63):
    PLAYER_PERMUTATION[i] = (16 * i) % 63
PLAYER_PERMUTATION[63] = 63 # Based on assumption

# --- DIMACS CNF Helper ---

class CnfGenerator:
    """A helper class to manage variable indices and generate DIMACS CNF clauses."""
    
    def __init__(self):
        self.next_var = 1
        self.clauses = []

    def new_var(self) -> int:
        """Allocates a new unique SAT variable index."""
        v = self.next_var
        self.next_var += 1
        return v

    def new_var_block(self, size: int) -> List[int]:
        """Allocates a block of variables of 'size'."""
        return [self.new_var() for _ in range(size)]

    def add_clause(self, clause: List[int]):
        """Adds a clause to the list."""
        self.clauses.append(clause)

    def get_dimacs(self) -> str:
        """Formats all clauses into a DIMACS CNF string."""
        header = f"p cnf {self.next_var - 1} {len(self.clauses)}\n"
        body = "\n".join(" ".join(map(str, c)) + " 0" for c in self.clauses)
        return header + body

    # --- NEW HELPER FUNCTIONS for key schedule ---
    def add_equiv_clauses(self, a: int, b: int):
        """Generates 2 CNF clauses for A <-> B (A = B)"""
        # (A' OR B) AND (A OR B')
        self.add_clause([-a, b])
        self.add_clause([a, -b])
        
    def add_notequiv_clauses(self, a: int, b: int):
        """Generates 2 CNF clauses for A <-> NOT B (A != B)"""
        # (A' OR B') AND (A OR B)
        self.add_clause([-a, -b])
        self.add_clause([a, b])
    # --- END NEW HELPER ---

    def add_xor_clauses(self, a: int, b: int, c: int):
        """Generates 4 CNF clauses for A = B XOR C"""
        self.add_clause([-a, -b, -c])
        self.add_clause([-a, b, c])
        self.add_clause([a, -b, c])
        self.add_clause([a, b, -c])

    def add_sbox_clauses(self, inputs: List[int], outputs: List[int]):
        """Generates 64 CNF clauses for one 4-bit S-box."""
        if len(inputs) != 4 or len(outputs) != 4:
            raise ValueError("S-box must be 4-bit in/out")
            
        for x_val in range(16):
            y_val = SBOX_TABLE[x_val]
            
            premise = []
            for i in range(4):
                bit_index = 3 - i # Map to x3, x2, x1, x0
                if (x_val >> i) & 1:
                    premise.append(-inputs[bit_index])
                else:
                    premise.append(inputs[bit_index])

            for i in range(4):
                bit_index = 3 - i # Map to y3, y2, y1, y0
                conclusion_literal = outputs[bit_index]
                if not ((y_val >> i) & 1):
                    conclusion_literal = -conclusion_literal
                
                self.add_clause(premise + [conclusion_literal])

    def add_player_clauses(self, inputs: List[int], outputs: List[int]):
        """Generates 128 CNF clauses for the 64-bit P-layer."""
        if len(inputs) != 64 or len(outputs) != 64:
            raise ValueError("P-layer must be 64-bit in/out")

        for i in range(64):
            s_i = inputs[i]
            p_i = PLAYER_PERMUTATION[i]
            z_pi = outputs[p_i]
            
            self.add_equiv_clauses(s_i, z_pi) # A <-> B is (A' v B) & (A v B')

    def add_unit_clause_str(self, bit_str: str, var_list: List[int]):
        """Sets a fixed bit string (like plaintext) as unit clauses."""
        if len(bit_str) != len(var_list):
            raise ValueError("Bit string and var list length mismatch")
        
        for i, bit_char in enumerate(bit_str):
            var = var_list[i]
            if bit_char == '0':
                self.add_clause([-var])
            else:
                self.add_clause([var])

# --- Main Program ---

def main():
    try:
        if len(sys.argv) != 3:
            raise ValueError(f"Expected 2 arguments, but got {len(sys.argv) - 1}")
        
        ROUNDS = int(sys.argv[1])
        testcase_filename = sys.argv[2] 

        if not (1 <= ROUNDS <= 100000): # Allow 1 round for testing
            raise ValueError("Rounds must be at least 1")

    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        print(f"\nUsage: python {sys.argv[0]} <rounds> <testcase_filename>", file=sys.stderr)
        print(f"Example: python {sys.argv[0]} 6 data/testcases/testcase1.txt", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"An unexpected error occurred: {e}", file=sys.stderr)
        return 1

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    output_dir = os.path.join(project_root, "out", "cnf")
    os.makedirs(output_dir, exist_ok=True)

    base_testcase_name = os.path.splitext(os.path.basename(testcase_filename))[0]
    output_filename = os.path.join(
        output_dir, f"present_r{ROUNDS}_{base_testcase_name}_keysched.cnf"
    )

    print(f"Reading test case from: {testcase_filename}", file=sys.stderr)
    try:
        with open(testcase_filename, 'r') as f:
            PLAINTEXT_STR = f.readline().strip()
            CIPHERTEXT_STR = f.readline().strip()
        
        if len(PLAINTEXT_STR) != 64: raise ValueError(f"Plaintext line is not 64 bits (got {len(PLAINTEXT_STR)})")
        if len(CIPHERTEXT_STR) != 64: raise ValueError(f"Ciphertext line is not 64 bits (got {len(CIPHERTEXT_STR)})")
            
    except FileNotFoundError:
        print(f"Error: Test case file not found at '{testcase_filename}'", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error reading file {testcase_filename}: {e}", file=sys.stderr)
        return 1

    
    cnf = CnfGenerator()

    # --- 1. Allocate all variables ---
    
    # --- KEY SCHEDULE MODIFICATION START ---
    
    # 1a. Create the single 80-bit Master Key (k_0 ... k_79)
    # These are the *only* unknown key bits the solver needs to find.
    master_key = cnf.new_var_block(80)
    
    # 1b. Create (R+1) 80-bit key registers to hold the state at each round
    # key_registers[0] is the master key
    # key_registers[1] is the state after 1 update
    # ...
    # key_registers[ROUNDS] is the state for the final (R+1)-th key
    key_registers = [cnf.new_var_block(80) for _ in range(ROUNDS + 1)]
    
    # 1c. Constrain the first key register to be the master key
    # key_registers[0] <-> master_key
    for i in range(80):
        cnf.add_equiv_clauses(key_registers[0][i], master_key[i])

    # --- KEY SCHEDULE MODIFICATION END ---
    

    # Intermediate states for R rounds (encryption path)
    xor_out_states = [cnf.new_var_block(64) for _ in range(ROUNDS)]
    sbox_out_states = [cnf.new_var_block(64) for _ in range(ROUNDS)]
    play_out_states = [cnf.new_var_block(64) for _ in range(ROUNDS)]
    
    # Final xor state (i.e., ciphertext)
    final_xor_state = cnf.new_var_block(64)

    # --- 2. Set known values (unit clauses) ---
    plaintext_vars = cnf.new_var_block(64)
    cnf.add_unit_clause_str(PLAINTEXT_STR, plaintext_vars)
    cnf.add_unit_clause_str(CIPHERTEXT_STR, final_xor_state)

    # --- 3. Build CNF clauses for KEY SCHEDULE (PRESENT-80) ---
    # We loop from 1 to ROUNDS (inclusive) to generate 
    # key_registers[1] up to key_registers[ROUNDS]
    
    print(f"Generating CNF for PRESENT-80 key schedule...", file=sys.stderr)
    for i in range(1, ROUNDS + 1):
        current_reg = key_registers[i-1] # Reg state from previous round
        next_reg = key_registers[i]      # Reg state we are constraining
        
        # --- Step 1: 61-bit left rotation ---
        # [k_79 ... k_0] = [k_18 ... k_0 k_79 ... k_19]
        rotated_reg = cnf.new_var_block(80)
        for j in range(80):
            # (j + 61) % 80 is the new position of bit j after rotation
            # We map it back: bit j in new reg comes from bit (j - 61) % 80 in old reg
            # Python's % operator handles negative numbers correctly
            source_index = (j - 61) % 80 
            cnf.add_equiv_clauses(rotated_reg[j], current_reg[source_index])
            
        # --- Step 2: S-box substitution ---
        # Pass 4 MSBs (k_79..k_76) through S-box
        sboxed_reg = cnf.new_var_block(80)
        sbox_in = [rotated_reg[79], rotated_reg[78], rotated_reg[77], rotated_reg[76]]
        sbox_out = cnf.new_var_block(4) # y3, y2, y1, y0
        cnf.add_sbox_clauses(sbox_in, sbox_out)
        
        # Constrain the new s-boxed register
        # 4 MSBs are replaced by sbox_out
        cnf.add_equiv_clauses(sboxed_reg[79], sbox_out[0]) # y3
        cnf.add_equiv_clauses(sboxed_reg[78], sbox_out[1]) # y2
        cnf.add_equiv_clauses(sboxed_reg[77], sbox_out[2]) # y1
        cnf.add_equiv_clauses(sboxed_reg[76], sbox_out[3]) # y0
        # Other 76 bits pass through unchanged
        for j in range(76):
            cnf.add_equiv_clauses(sboxed_reg[j], rotated_reg[j])

        # --- Step 3: XOR with 5-bit round_counter i ---
        # XORed with bits k_19..k_15
        rc = i # The round counter (1-based)
        # Get 5 bits of rc, e.g., i=1 -> [0,0,0,0,1]
        rc_bits = [(rc >> bit) & 1 for bit in range(4, -1, -1)] 
        
        for j in range(80):
            source_var = sboxed_reg[j]
            target_var = next_reg[j]
            
            if 15 <= j <= 19:
                # Bit j=19 maps to rc_bits[0] (MSB of counter)
                # Bit j=15 maps to rc_bits[4] (LSB of counter)
                rc_bit_val = rc_bits[4 - (j - 15)]
                
                if rc_bit_val == 0:
                    # XOR with 0 -> A <-> B
                    cnf.add_equiv_clauses(target_var, source_var)
                else:
                    # XOR with 1 -> A <-> NOT B
                    cnf.add_notequiv_clauses(target_var, source_var)
            else:
                # Other 75 bits pass through
                cnf.add_equiv_clauses(target_var, source_var)
    
    print(f"Generating CNF for encryption path...", file=sys.stderr)
    # --- 4. Build CNF clauses for R rounds (Encryption Path) ---
    
    current_state_vars = plaintext_vars

    for r in range(ROUNDS):
        # Get variables for the current round
        # k_r is the 64 MSBs (k_79..k_16) of the key register for this round
        # For round 0 (encryption round 1), we use key_registers[0] (K_1)
        k_r = key_registers[r][16:] # Python slice [16:] gets bits 16..79
        
        xor_out_r = xor_out_states[r]
        sbox_out_r = sbox_out_states[r]
        play_out_r = play_out_states[r]
        
        # 4a. AddRoundKey 
        for i in range(64):
            cnf.add_xor_clauses(xor_out_r[i], current_state_vars[i], k_r[i])
            
        # 4b. sBoxLayer 
        for i in range(16):
            inputs = xor_out_r[i*4 : (i+1)*4]
            outputs = sbox_out_r[i*4 : (i+1)*4]
            cnf.add_sbox_clauses(inputs, outputs)

        # 4c. pLayer 
        cnf.add_player_clauses(sbox_out_r, play_out_r)
        
        current_state_vars = play_out_r

    # --- 5. Build clauses for final AddRoundKey ---
    # We use the (R+1)-th key, which is in key_registers[ROUNDS]
    final_key = key_registers[ROUNDS][16:] # Get bits 16..79 from the final register
    
    for i in range(64):
        cnf.add_xor_clauses(final_xor_state[i], current_state_vars[i], final_key[i])

    # --- 6. Output DIMACS CNF ---
    print(f"Writing CNF output to file: {output_filename}", file=sys.stderr)
    try:
        with open(output_filename, 'w') as f:
            f.write(cnf.get_dimacs())
    except IOError as e:
        print(f"Error writing to file {output_filename}: {e}", file=sys.stderr)
        return 1
    
    print(f"--- Comments (not DIMACS format) ---", file=sys.stderr)
    print(f"Successfully generated CNF for {ROUNDS} rounds of PRESENT (with Key Schedule).", file=sys.stderr)
    print(f"Total variables: {cnf.next_var - 1}", file=sys.stderr)
    print(f"Total clauses: {len(cnf.clauses)}", file=sys.stderr)
    # <--- CHANGED: The only unknown is the 80-bit master key ---
    print(f"Unknown key variables: 80 (Master Key, variables 1 to 80)", file=sys.stderr)
    print(f"--- End of comments ---", file=sys.stderr)

if __name__ == "__main__":
    sys.exit(main())