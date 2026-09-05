Require Import Lia.
Require Import Arith.

(* === Tier 1: zero/fixed-arg wrappers around real automation === *)
Tactic Notation "solve_arith" := lia.
Tactic Notation "solve_auto" := auto.

(* === Tier 2: fixed-arity wrapper with two term arguments === *)
Tactic Notation "combine_facts" constr(e1) constr(e2) := exact (conj e1 e2).

(* === Tier 3: recursive, tactic-taking wrapper -- direct analog of
   Lean's `focus_then t:tacticSeq : tactic => (tactic| \u00b7 $t)` === *)
Tactic Notation "then_do" tactic(t) := t.

(* === Tier 4: a wrapper with a numeric/ident argument, testing a
   different argument kind than constr === *)
Tactic Notation "induct_on" ident(x) := induction x.

Theorem test_arith : forall n : nat, n + 0 = n.
Proof. solve_arith. Qed.

Theorem test_auto : True.
Proof. solve_auto. Qed.

Theorem test_combine : (3 = 3) /\ (4 = 4).
Proof. combine_facts (eq_refl 3) (eq_refl 4). Qed.

Theorem test_then_do : forall n : nat, n = n.
Proof. then_do reflexivity. Qed.

Theorem test_induct : forall n : nat, n + 0 = n.
Proof.
  induct_on n.
  - reflexivity.
  - simpl. rewrite IHn. reflexivity.
Qed.
