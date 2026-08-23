import sys
sys.path.insert(0, "/home/stanley")
from kernel_loop import Repl, run_proof

repl = Repl("/home/stanley/Pantograph/.lake/build/bin/repl",
            ("Init", "Mathlib.Algebra.Group.Basic"), timeout=300,
            lean_path="/home/stanley/mathlib4-v423")
expr = ("∀ {M : Type} [MulOneClass M] (P : Prop) [Decidable P] (a b : M), "
        "ite P (a * b) 1 = ite P a 1 * ite P b 1")
for rec in run_proof(repl, expr,
        ["intro M _ P _ a b", "by_cases h : P", "simp [h]", "simp [h]"]):
    print(rec)
repl.close()