#!/usr/bin/env python3

import sys
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

    def add_xor_clauses(self, a: int, b: int, c: int):
        """
        Generates 4 CNF clauses for A = B XOR C.
        A <-> (B XOR C)
        These 4 clauses exclude the 4 invalid combinations of A, B, C.
         (Corrected typo from PDF)
        (A' + B' + C') -> (A=1, B=1, C=1) is False
        (A' + B + C)   -> (A=1, B=0, C=0) is False
        (A + B' + C)   -> (A=0, B=1, C=0) is False
        (A + B + C')   -> (A=0, B=0, C=1) is False
        """
        self.add_clause([-a, -b, -c]) # (Variant of first clause)
        self.add_clause([-a, b, c])   # (Second clause)
        self.add_clause([a, -b, c])   # (Variant of third clause)
        self.add_clause([a, b, -c])   # (Variant of fourth clause)

    def add_sbox_clauses(self, inputs: List[int], outputs: List[int]):
        """
        Generates 64 CNF clauses for one 4-bit S-box.
        inputs = [x3, x2, x1, x0]
        outputs = [y3, y2, y1, y0]
        
        """
        if len(inputs) != 4 or len(outputs) != 4:
            raise ValueError("S-box must be 4-bit in/out")
            
        # Iterate through all 16 entries in the S-box table 
        for x_val in range(16):
            y_val = SBOX_TABLE[x_val]
            
            # Create the premise clauses for "IF X = x_val"
            # (x3' OR x2 OR x1 OR x0) for X=0111 (7)
            # This is (NOT (X == x_val))
            #  (x3+x2+x1+x0+...)
            premise = []
            for i in range(4):
                # x3, x2, x1, x0 
                bit_index = 3 - i
                if (x_val >> i) & 1:
                    premise.append(-inputs[bit_index]) # x_i is 1 -> literal is -x_i
                else:
                    premise.append(inputs[bit_index])  # x_i is 0 -> literal is x_i

            # Create the 4 conclusion clauses for "THEN Y = y_val"
            # (premise OR y3)
            # (premise OR y2')
            # ...
            for i in range(4):
                # y3, y2, y1, y0 
                bit_index = 3 - i
                conclusion_literal = outputs[bit_index]
                if not ((y_val >> i) & 1):
                    conclusion_literal = -conclusion_literal
                
                # 4 clauses are generated per S-box entry 
                self.add_clause(premise + [conclusion_literal])

    def add_player_clauses(self, inputs: List[int], outputs: List[int]):
        """
        Generates 128 CNF clauses for the 64-bit P-layer.
        Z[P(i)] <-> S[i]
        
        """
        if len(inputs) != 64 or len(outputs) != 64:
            raise ValueError("P-layer must be 64-bit in/out")

        for i in range(64):
            s_i = inputs[i]
            p_i = PLAYER_PERMUTATION[i]
            z_pi = outputs[p_i]
            
            # Z[P(i)] <-> S[i]
            # (NOT S[i] OR Z[P(i)]) AND (S[i] OR NOT Z[P(i)])
            self.add_clause([-s_i, z_pi])
            self.add_clause([s_i, -z_pi])

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
        if len(sys.argv) != 2:
            raise ValueError()
        ROUNDS = int(sys.argv[1])
        # --- Modification Start ---
        # As requested, increased round limit from 10 to 100000
        if not (6 <= ROUNDS <= 100000):
        # --- Modification End ---
            # 
            raise ValueError()
    except ValueError:
        # --- Modification Start ---
        # Update error message to reflect new range
        print("Error: You must provide a number of rounds r (r must be between 6 and 100000).", file=sys.stderr)
        # --- Modification End ---
        print(f"Usage: python {sys.argv[0]} <rounds>", file=sys.stderr)
        print(f"Example: python {sys.argv[0]} 7 > present_r7.cnf", file=sys.stderr)
        return 1

    # --- CHANGE 1: Automatically generate filename here ---
    output_filename = f"present_r{ROUNDS}.cnf"
    
    # Your provided test case
    PLAINTEXT_STR = "1010101110101001011000110111100001011101010100101101010101101101"
    CIPHERTEXT_STR = "0100101100110010101110111010001010001111010100100101000101110010"
    
    cnf = CnfGenerator()

    # --- 1. Allocate all variables ---
    # (R+1) 64-bit round keys (K_1 ... K_{R+1})
    # 
    keys = [cnf.new_var_block(64) for _ in range(ROUNDS + 1)]
    
    # Intermediate states for R rounds
    # xor_out[r] = state[r] XOR key[r]
    xor_out_states = [cnf.new_var_block(64) for _ in range(ROUNDS)]
    # sbox_out[r] = sBoxLayer(xor_out[r])
    sbox_out_states = [cnf.new_var_block(64) for _ in range(ROUNDS)]
    # play_out[r] = pLayer(sbox_out[r])
    play_out_states = [cnf.new_var_block(64) for _ in range(ROUNDS)]
    
    # Final xor state (i.e., ciphertext)
    # 
    final_xor_state = cnf.new_var_block(64)

    # --- 2. Set known values (unit clauses) ---

    # Set Plaintext as input to the first round
    # 
    plaintext_vars = cnf.new_var_block(64)
    cnf.add_unit_clause_str(PLAINTEXT_STR, plaintext_vars)
    
    # Set Ciphertext as the output of the final addRoundKey
    # 
    cnf.add_unit_clause_str(CIPHERTEXT_STR, final_xor_state)

    # --- 3. Build CNF clauses for R rounds ---
    
    current_state_vars = plaintext_vars

    for r in range(ROUNDS):
        # Get variables for the current round
        k_r = keys[r]                 # K_{r+1}
        xor_out_r = xor_out_states[r]
        sbox_out_r = sbox_out_states[r]
        play_out_r = play_out_states[r]
        
        # 3a. AddRoundKey 
        # xor_out_r = current_state_vars XOR k_r
        for i in range(64):
            cnf.add_xor_clauses(xor_out_r[i], current_state_vars[i], k_r[i])
            
        # 3b. sBoxLayer 
        # sbox_out_r = sBoxLayer(xor_out_r)
        for i in range(16): # 16 S-boxes
            inputs = xor_out_r[i*4 : (i+1)*4]
            # --- Bug fix: Removed stray 'H' ---
            outputs = sbox_out_r[i*4 : (i+1)*4]
            cnf.add_sbox_clauses(inputs, outputs)

        # 3c. pLayer 
        # play_out_r = pLayer(sbox_out_r)
        cnf.add_player_clauses(sbox_out_r, play_out_r)
        
        # Update input for the next round
        current_state_vars = play_out_r

    # --- 4. Build clauses for final AddRoundKey ---
    # 
    # final_xor_state (Ciphertext) = current_state_vars (play_out[ROUNDS-1]) XOR keys[ROUNDS] (K_{R+1})
    final_key = keys[ROUNDS]
    for i in range(64):
        cnf.add_xor_clauses(final_xor_state[i], current_state_vars[i], final_key[i])

    # --- 5. Output DIMACS CNF ---
    
    # --- CHANGE 2: Changed print() to 'with open(...) as f:' ---
    print(f"Writing CNF output to file: {output_filename}", file=sys.stderr)
    try:
        with open(output_filename, 'w') as f:
            f.write(cnf.get_dimacs())
    except IOError as e:
        print(f"Error writing to file {output_filename}: {e}", file=sys.stderr)
        return 1
    # --- Change End ---
    
    print(f"--- Comments (not DIMACS format) ---", file=sys.stderr)
    print(f"Successfully generated CNF for {ROUNDS} rounds of PRESENT.", file=sys.stderr)
    print(f"Total variables: {cnf.next_var - 1}", file=sys.stderr)
    
    # --- BUG FIX: Changed 'self.clauses' to 'cnf.clauses' ---
    print(f"Total clauses: {len(cnf.clauses)}", file=sys.stderr)
    # --- End of Bug Fix ---
    
    print(f"Unknown key variables: {64 * (ROUNDS + 1)} (variables 1 to {64 * (ROUNDS + 1)})", file=sys.stderr)
    print(f"--- End of comments ---", file=sys.stderr)

if __name__ == "__main__":
    sys.exit(main())