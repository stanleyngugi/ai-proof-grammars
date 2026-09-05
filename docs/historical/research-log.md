# Grammar-Constrained, Kernel-Verified Lean Proving: A Research Log

*What was proposed, what we actually built and ran, what broke, what we learned, and what remains open.*

---

## 0. How to read this document

This is not a clean writeup of a plan. It's a research log — the original architectural thesis, followed by everything that happened when we actually tried to build and test pieces of it: real code, real Mathlib source, real toolchains, real bugs (several of them ours), and real live model calls. Where the original thesis's claims held up, that's stated plainly. Where our own tooling was wrong — and it was wrong multiple times, in a specific and recurring way — that's stated just as plainly. The goal is calibration, not a victory lap.

---

## 1. The Original Thesis

A document proposed a four-layer architecture for LLM-driven Lean 4 theorem proving:

- **Layer 0 — Solver Reconnaissance**: run fast decision procedures (`omega`, `linarith`, `ring`, `decide`), ATPs (Zipperposition via Lean-Auto), SMT (cvc5 via QuerySMT), and neural premise selection (LeanHammer) on *every* goal, before the LLM generates anything. Claimed ~53% of Mathlib goals close without any LLM involvement.
- **Layer 1 — Grammar Constraints**: constrain LLM token generation to a CFG covering the Lean tactic sublanguage (~40–60 productions, keyword-dispatched, permissive term arguments), guaranteeing 100% syntactic validity.
- **Layer 2 — Kernel Verification**: every generated tactic is executed against the real Lean kernel via Pantograph, producing precise, step-level diagnostics rather than whole-proof pass/fail.
- **Layer 3 — Solver-as-Teacher Training**: all kernel-verified proofs (solver- and LLM-generated) become supervised fine-tuning data, with solver dependency decreasing across generations as the LLM internalizes proof patterns.

Central claims worth tracking against evidence:
- Top 20 Mathlib tactics cover ~83% of usage (Lean4trace, ICML 2024).
- 47.3% of prover errors are hallucinated identifiers; 32.7% misapplied tactics; 15.2% incomplete outputs (`sorry`); 4.8% syntax errors (Construction-Verification/AMBER benchmark).
- No published work applies grammar-constrained decoding to Lean/Coq/Isabelle proof *tactic* generation as of early 2026.

We spot-checked three of this document's most load-bearing citations against live web search — LeanHammer (arXiv:2506.07477), "Attention Meets Reachability" (arXiv:2603.05540), and the Mathlib Initiative's $5M Renaissance Philanthropy funding — and all three checked out precisely, including specific figures. This is a well-sourced document, not a confabulated one. One section, §6.6 ("Internalization Theory" — the claim that training on kernel-verified proofs produces reasoning that generalizes to legal/medical/general domains), was later withdrawn by its own author as incorrect; nothing in our experimental work depended on it, and nothing here defends it.

---

## 2. What We Actually Tested, and How

We did not have API credentials in the bash sandbox and did not have a Lean kernel available in the browser artifact environment — a real infrastructure split that shaped everything below. The two environments were bridged manually, by running live model calls in browser artifacts and relaying transcripts back into the chat for kernel-side testing, or by hand-typing specific tactic proposals into a real REPL session.

Everything reported below is either:
- **Code we wrote and ran ourselves** in a Linux sandbox (Python, Lean, `lake`, `bash`), against real, freshly-cloned Mathlib4 and Batteries source, or
- **Live API calls** made from browser-rendered artifacts against the real Claude API, with results relayed back by the user, or
- **Direct interaction** with a real, from-source-built Lean 4 toolchain and Pantograph binary.

No numbers below are simulated, estimated from documentation, or asserted without a corresponding command/output.

---

## 3. Layer 1: The Grammar

### 3.1 Design

A Lark/Earley grammar mirroring the thesis's §10.1 structure: `KEYWORD ARGS`, with `ARGS` as a permissive catch-all, plus a small number of recursive productions (`·` focus bullets, `| pattern => tactic` case arms). Named productions carry explicit shape (`rw ARGS`, `simp ARGS?`, etc.); anything else falls through to a generic `IDENT ARGS?` catch-all.

### 3.2 Pilot: 9 hand-picked files

Real, current Mathlib4 source across algebra, order, topology, measure theory, probability, number theory (~6,700 lines). First pass with 19 hand-written productions: **73.8% named, 15.0% fallback, 11.2% parse failure**. Iterating on real failure cases (adding the `·` focus bullet as a real recursive production, then 15 more productions for tactics found in the fallback bucket) brought this to **34 productions → 96.4% combined structural coverage**, with every remaining failure traced to a line-splitting artifact, not a missing tactic.

### 3.3 Full scale: the entire Mathlib4 repository

Rather than stop at a sample, we shallow-cloned the full `leanprover-community/mathlib4` repository: **8,302 files, 464,950 lines**. First extraction pass (bracket-balance line merging only) gave 229,560 candidate tactic lines; classifying these surfaced two real bugs, not just missing coverage:

1. **A genuine grammar gap**: no production for `| pattern => tactic` (match/induction case arms) — 36% of failures.
2. **An extraction bug**: bracket-balance merging missed continuations that don't have literal unclosed brackets but are still part of the previous tactic under Lean's real indentation rule (`colGt`) — 51% of failures.

Both were fixed: a `case_arm_tac` production was added, and the line-merger was rewritten to use real colGt-style indentation continuation, not just bracket counting. This dropped the reported line count to a corrected **144,154 genuinely-distinct logical tactic lines** (the earlier 229,560 had been inflated by artificial line-splits).

**Final result, 53 hand-written productions, full Mathlib scale:**

| | Count | % |
|---|---|---|
| Named production match | 133,224 | 92.4% |
| Fallback (generic keyword-dispatch) | 10,725 | 7.4% |
| True parse failure | 205 | 0.14% |
| **Structural coverage (named + fallback)** | **143,949** | **99.86%** |

All 205 residual failures were hand-audited individually. None represent a missing tactic keyword — they split across lone `·` bullets with nothing on the merged line (extraction edge case, 48), anonymous structure/instance literals in term mode (45), deprecation/compiler directives like `#adaptation_note` (26), docstring fragments leaking into the scan (15), `calc`-step continuations (3), and 68 genuinely miscellaneous cases.

**Cross-validation on keyword concentration** (a separate, simpler measure than grammar-fit): top-20 leading keywords covered 84.9% of lines at full scale, top-40 covered 94.0%. This is close to, and independently corroborates, the thesis's cited Lean4trace figure of ~83% for top-20 — three separate measurements (9-file pilot: 87%, full-Mathlib: 84.9%, external Lean4trace citation: ~83%) now converge.

### 3.4 Does it generalize to LLM-generated tactics, not just human-written ones?

A live-API artifact (real Claude calls, not simulated) proposed a first tactic for 14 real Mathlib theorem statements. Classified against the same 53-production grammar: **93% named, 7% fallback, 0% outside grammar** on a clean run — consistent with, and marginally better than, the human-corpus baseline (small sample; not a statistically distinguishable difference, but no sign of divergence either).

---

## 4. The Macro Bridge

### 4.1 The pattern

One-line Lean macros promote tactics outside the hand-written grammar into CFG-friendly keyword forms, expanding to real Lean at parse time:

```lean
macro "solve_positivity" : tactic => `(tactic| positivity)
macro "apply_gcongr" t:term : tactic => `(tactic| gcongr $t)
macro "discharge_linear" e1:term:max e2:term:max : tactic =>
  `(tactic| linarith [$e1, $e2])
macro "focus_then" t:tacticSeq : tactic => `(tactic| · $t)
```

### 4.2 A real bug, found by a real compiler

`elan`'s toolchain resolver requires `release.lean-lang.org`, outside the sandbox's network allowlist — but Lean's actual binaries are ordinary GitHub Release assets. Fetching `lean-4.32.2-linux.zip` directly from GitHub and registering it via `elan toolchain link` bypassed the blocked manifest entirely and gave a real, working Lean 4.32.2 compiler.

Elaborating the macro-bridge pattern for real caught a genuine bug: `macro "combine_facts" e1:term e2:term : tactic => ...` parsed `combine_facts hp hq` as **one** term (`hp` applied to `hq`), not two separate arguments — because bare `term` doesn't respect macro-argument boundaries. Lean's own error was precise: `Function expected at hp`. Fix, verified: `term:max` on each argument, which restricts each slot to atomic/application-as-a-unit precedence. Confirmed with exit code 0 after the fix; confirmed the bug was real by reproducing it first, then fixing it, then re-testing.

### 4.3 Verified against real, from-source-built Mathlib tactics

Estimating the build cost for `positivity`/`gcongr`/`linarith` initially went wrong: a Python dependency-closure script reported **1,329 files** for three unrelated targets — an identical number across different targets, which should have been caught immediately as a bug rather than reported as a finding. Once we stopped trusting the script and asked `lake` directly, real job counts were far smaller: 716 for `Positivity.Basic`, 814 for `Linarith`, 107 for `GCongr`. Total wall-clock across several checkpointed `lake build` calls (build artifacts persist across separate tool invocations even though background processes don't): roughly 20 minutes, not the ~8.5 hours the buggy estimate implied.

With real tactics built from source, `macro_bridge_VERIFIED.lean` compiles and passes, exit code 0:

```lean
import Mathlib.Tactic.Positivity.Basic
import Mathlib.Tactic.GCongr
import Mathlib.Tactic.Linarith

macro "solve_positivity" : tactic => `(tactic| positivity)
macro "apply_gcongr" t:term : tactic => `(tactic| gcongr $t)
macro "discharge_linear" e1:term:max e2:term:max : tactic =>
  `(tactic| linarith [$e1, $e2])
macro "focus_then" t:tacticSeq : tactic => `(tactic| · $t)

example (a b : ℤ) (ha : 0 < a) (hb : 0 < b) : 0 < a + b := by solve_positivity
example (a b c : ℤ) (h : a ≤ b) (hc : 0 ≤ c) : c * a ≤ c * b := by apply_gcongr c * ?_
example (x y : ℤ) (h1 : x ≤ y) (h2 : (0:ℤ) ≤ 1) : x ≤ y + 1 := by discharge_linear h1 h2
```

One genuinely useful negative result: the first attempt used `ℝ` and failed with instance-synthesis errors, because `Positivity.Basic` alone doesn't pull in `Mathlib.Data.Real.Basic`'s instances. Switching to `ℤ`/`ℕ` (whose instances were in the built graph) fixed it — a real fact about Mathlib's import structure, not a workaround.

---

## 5. Layer 2: Semantic and Kernel Verification

### 5.1 Discriminative testing on real proof text

Rather than test only cases expected to pass, we pulled a real theorem+proof pair verbatim from `Mathlib/Algebra/Group/Basic.lean` (`ite_mul_one`) and ran six candidate tactics against the same goal, checking each independently against the real kernel:

| Candidate tactic | Result |
|---|---|
| `by_cases h : P <;> simp [h]` (the real Mathlib proof) | **PASS** |
| `simp` | FAIL — unsolved goals |
| `tauto` | FAIL — unsolved goals |
| `constructor` | FAIL — no applicable constructor |
| `rfl` | FAIL — not definitionally equal |
| `trivial` | FAIL — assumption failed |

Five plausible-looking tactics genuinely fail with distinct, correct type-theoretic errors; only the real proof passes. This is discrimination, not a rigged demo.

### 5.2 Testing real LLM output against the real kernel

Given real transcripts of Claude's actual proposed tactics (relayed back from a browser artifact), 8 were tested by hand against the kernel, using the appropriate Mathlib pieces already built. Properly reclassified — distinguishing genuine errors from valid-but-incomplete "first step" proposals (the prompt asked for a first tactic, not a full proof):

- **2/8 fully closed the goal** in one shot.
- **4/8 were legitimate, error-free partial progress** (`split_ifs`, `simp [apply_ite]`, `constructor`, `induction b` all ran cleanly, leaving sensible open subgoals — exactly what a human would do as a first move).
- **2/8 were genuine errors — and the interesting kind**: `ite_ite_same` and `lt_of_not_le` do not exist anywhere in Mathlib (confirmed via `grep` across the full source tree, zero matches, any namespace). Claude didn't choose the wrong *tactic category* — the CFG matched all 8 proposals structurally, 100%. It invented specific *lemma names* that sound plausible but aren't real.

This is the single clearest empirical result from the whole session: **grammar-fit and semantic correctness are separate axes.** A CFG cannot see a hallucinated identifier, because `IDENT` inside a permissive `ARGS` slot is syntactically indistinguishable whether the identifier is real or invented.

---

## 6. Chasing the Hallucination Problem — and Finding Our Own Bugs Along the Way

### 6.1 A reproducible failure

`lt_of_not_le` was proposed by Claude for the same goal in two **separate, independent runs**. Grepping the entirety of Mathlib source confirms it does not exist under any namespace. This is not noise — it's a specific, characterizable, repeatable failure mode (plausibly Mathlib3→4 naming drift, or "this really ought to exist" pattern completion).

### 6.2 Building an identifier-existence checker — and its own bugs

Since bash has no API credentials (confirmed directly: a raw `curl` to `api.anthropic.com` returns 401, no key available) and browser artifacts have no Lean kernel, a closed loop combining both in one place isn't achievable in this sandbox. As a substitute, we extracted every real declaration name from Mathlib + Batteries source — **160,716 unique short names**, regex-scanned from 8,562 files — and shipped it inside a browser artifact that checks every identifier an LLM proposal references, retrying with the real missing-name error fed back, up to 3 rounds.

This tool had **three real, demonstrable bugs**, found by adversarial testing, not by chance:

1. **A silently-swallowed API error.** `(data.content || [])` with no HTTP-status or error-type check meant a failed call (rate-limiting, most likely, from rapid successive runs) became an empty string — which trivially "passes" the identifier check since there's nothing to flag. A run reported "14/14 clean" when in fact every call had failed. Fixed by explicitly checking `res.ok` and `data.type === "error"`, surfacing a distinct, visually separate "API error" verdict.
2. **A namespace-blind false negative.** The checker approved `Finset.log_prod` as valid, because a short-name-only lookup found *a* declaration named `log_prod` — but the real declaration lives in `namespace Real`, not `Finset`. This is the more dangerous class of bug: wrong information passed as verified.
3. **A false-positive on locally-bound variables.** In a goal with nested `fun h hdc => ...`, the checker flagged `hdc`, `hac`, `hd` as "hallucinated lemmas" — they were fresh lambda-bound variables introduced *inside* the tactic term, not global references. The extractor only stripped binder names declared in the *goal's* own signature, not ones introduced fresh within the tactic body.

### 6.3 A methodological flaw in the benchmark itself

One goal (`tendsto_pow_log_div_mul_add_atTop`) was "solved" by Claude citing a tactic with the goal's own exact name — because the goal statement was lifted verbatim from real, already-proven Mathlib source, and the model had plausibly memorized it. This is API recall, not proof construction, and it's a real contamination risk for any eval built from goals drawn from a corpus the model may have seen in training — not unique to this session, but this session ran directly into a small, concrete instance of it.

### 6.4 The pattern across all three bugs

None of the bugs above were in the Lean kernel or in Pantograph — every one was in throwaway Python/JS scaffolding written specifically for this session's experiments. But the *shape* of all three bugs is the same: **each one made the system look more correct than it actually was.** A dependency-closure script overestimating cost by 4x is merely wasteful; an API-error handler that converts failure into false "clean" and a namespace-blind checker that approves a wrong name are actively dangerous, because they fail in the direction of false confidence rather than false alarm. This is a general property worth naming: verification-layer code sits between an untrusted generator and a trusted oracle, and bugs in *that* layer silently launder bad output into apparently-good output. Any real system built on this architecture needs its own adversarial test suite for the checking layer itself, not just for the LLM's outputs.

---

## 7. Layer 2, For Real: Pantograph

### 7.1 Built from source

`leanprover/Pantograph`, cloned and built: 44/44 jobs, no Mathlib dependency at all for the tool itself (only a small test framework, LSpec). A real `.lake/build/bin/repl` executable resulted.

### 7.2 A real friction point the thesis doesn't dwell on

Pantograph pins an exact Lean version (`v4.29.1` in this build) and `.olean` files are binary-locked to that exact version. Our existing Mathlib build — done under `v4.33.0-rc1` for the macro-bridge work — was completely unusable against it: `uncaught exception: failed to read file '...Basic.olean', incompatible header`. Solving this required finding the specific historical Mathlib git *tag* (`v4.29.1` is a real Mathlib release, not just a Lean version) and rebuilding the needed module (`Mathlib.Algebra.Group.Basic`, 277 real build jobs) from scratch against the matching toolchain.

### 7.3 A real theorem, proven live, tactic-by-tactic

Using Pantograph's actual JSON protocol:

```
goal.start {"expr": "∀ {M : Type} [MulOneClass M] (P : Prop) [Decidable P] (a b : M), ite P (a * b) 1 = ite P a 1 * ite P b 1"}
goal.tactic {"stateId": 0, "tactic": "intro M _ P _ a b"}
goal.tactic {"stateId": 1, "tactic": "by_cases h : P"}
goal.tactic {"stateId": 2, "goalId": 0, "tactic": "simp [h]"}
goal.tactic {"stateId": 3, "goalId": 0, "tactic": "simp [h]"}
```

Final state: `"goals":[]` — the real `ite_mul_one` theorem, proven, matching Mathlib's actual proof (`by_cases h : P <;> simp [h]`) exactly, tactic-by-tactic, against a real, version-matched build.

A real mistake occurred and was corrected along the way: applying the second `simp [h]` back to the *original* branch-point state instead of the new state produced by closing the first branch, resulting in two disconnected partial explorations rather than one continuous proof. This is a genuinely instructive fact about the protocol: Pantograph's state model is a full DAG of exploration (excellent for tree search, exactly matching the thesis's "state branching" claims), and using it correctly requires tracking exactly which state ID resulted from which prior step — friction the thesis's clean pseudocode doesn't surface.

### 7.4 Structured, native error categorization — better than anything we built by hand

Feeding the exact same hallucination found earlier (`simp [ite_ite_same]`) through Pantograph directly:

```json
{"messages":[{"data":"Unknown identifier `ite_ite_same`","kind":"lean.unknownIdentifier._namedError","pos":{"column":6,"line":0},"severity":"error"}]}
```

This has a machine-readable `"kind"` field and an exact token position — a precise, structured, categorizable diagnostic, natively, for free. It supersedes the entire 160,716-name lookup table built in §6.2: that table was a workaround for not having live model access and a kernel in the same execution context, and it was never going to be as good as asking the real tool. Its namespace-blindness bug (§6.2, item 2) *cannot happen* here, because Pantograph resolves against the real environment rather than approximating it with a regex-derived table.

**Corrected understanding, stated precisely (this was clarified mid-session and matters):** every bug found this session was in code written for these experiments — never in the kernel, never in Pantograph. Both performed flawlessly, every time they were used directly. If anything, this session is evidence *for* the reliability of the substrate the original thesis proposes to build on, not evidence against the feasibility of grammar-plus-semantics checking in general.

---

## 8. Constrained Decoding: What We Actually Tried, and What the API Actually Supports

### 8.1 Clarifying the distinction

Everything in §3 was **post-hoc classification** — parsing already-generated text — never token-level logit masking. The original thesis's Layer 1 describes the latter: llguidance/XGrammar intervening in the sampling loop itself, requiring either white-box model access (self-hosted, open-weight) or an API that exposes grammar constraints natively.

### 8.2 Anthropic's real structured-outputs feature

Checked directly against current documentation: Anthropic shipped native grammar-constrained sampling — real logit masking, not prompting — as **Structured Outputs**, GA since November 2025 (`anthropic-beta: structured-outputs-2025-11-13`), via `strict: true` tool schemas and `output_config.format`. This is genuinely the mechanism the thesis describes, available through a hosted API, which the thesis's own survey (written from an "early 2026" vantage point) may not have had visibility into yet.

**Scope, confirmed precisely through testing, not assumption:**
- **Flat, bounded schemas work.** A tool with `tactic_keyword: {enum: [...53 productions...]}` plus a free-text `args` field is real, compiled, grammar-constrained sampling on the keyword slot.
- **Recursive schemas do not work.** Documented explicitly, independently, across multiple sources: *"No recursive schemas. Flatten hierarchical structures or limit nesting depth."* AWS Bedrock's implementation of the same models states the identical constraint. We confirmed this empirically: a `TacticNode` schema with `$ref` self-reference (for `induction ... with` case bodies) returned `stop_reason: end_turn` with no tool call — a soft failure, not the documented hard 400, which is itself a real gap in the API's error surfacing, but the root cause matches the documented limitation precisely.

### 8.3 The resolution: recursion belongs in the loop, not the schema

The failed recursive-schema test, properly diagnosed rather than written off, produces a genuinely useful architectural conclusion: **the tactic-by-tactic loop we validated with Pantograph in §7 already supplies the recursion externally.** `induction` produces new goal states; each becomes an independent, flat, bounded generation call. The tree structure that would need a recursive schema to represent in one shot instead lives in the *sequence of Pantograph states* across multiple calls. The flat schema isn't a workaround for a missing feature — it's the right granularity, once you have fast, per-step kernel feedback supplying the recursion at the orchestration level instead.

### 8.4 The sharper framing for why this matters (or doesn't) at all

A late-session reframing, worth stating as its own conclusion because it changes what's actually worth optimizing: since Lean tactics are near-independent steps against the kernel, the cost of an occasional malformed generation is *local* (one wasted round-trip) rather than cascading through a whole proof attempt, the way it would in monolithic whole-proof generation. This changes the value proposition of constrained decoding from "guarantee correctness" to "maximize the fraction of generated tokens that reach evaluable, kernel-checkable form" — training-data yield per token, not correctness by construction. Given our own data — Claude's live output was **100% structurally valid** in a clean run even without any constraint — the marginal value of paying constrained decoding's engineering cost is small for a frontier model on this specific task, and large for the weaker or less-specialized models the thesis's own cited data describes (APOLLO: general-purpose models default to Lean 3 syntax or trivial compilation errors 30–50% of the time). **Constrained decoding's value appears to scale inversely with how fluent the model already is at the target language** — not uniformly load-bearing, as the original thesis's framing implies.

Separately and unconditionally: grammar constraining, however implemented, cannot address the failure mode we actually found and reproduced. `simp [ite_ite_same]` is perfectly grammatical. Nothing about masking invalid tokens touches whether a specific identifier inside a valid slot happens to be real.

---

## 9. Layer 0: Solver Reconnaissance — First Real Measurement

Everything above touched Layers 1 and 2. Layer 0 — fast decision procedures running before the LLM generates anything, claimed to close ~53% of Mathlib goals — had no experimental evidence behind it at all until this point. Unlike Layers 0's full design (which also includes ATP via Zipperposition, SMT via cvc5, and LeanHammer's neural premise selection, none of which we have infrastructure for), the cheapest tier — fast, built-in tactics — is fully testable with what we already had built.

### 9.1 Design

Rather than hand-pick favorable goals, we took an unbiased random sample (seeded) of 25 real, tactic-mode theorems from `Mathlib/Algebra/Group/Basic.lean` (147 qualifying candidates total), swapped each one's real proof for a candidate fast tactic, and compiled against the real kernel. No cherry-picking: every theorem in the file with a `:= by` proof was eligible, and the sample was drawn mechanically.

**Solver list, corrected by direct research rather than assumed from the original thesis's table:** `polyrith` was dropped — confirmed dead, its external Sage backend was shut down and it no longer functions in current Mathlib at all. `ac_rfl` and `grind` were added — both are core Lean (not Mathlib), requiring no import, and were missing from the thesis's list. `abel`, `ring`, and `group` were added with their required imports. Final set: `simp`, `aesop`, `decide`, `rfl`, `trivial`, `tauto`, `omega`, `ac_rfl`, `grind`, `abel`, `abel_nf`, `ring`, `ring_nf`, `group`.

### 9.2 A three-bug chain — found and fixed live, in sequence

This sub-experiment is the clearest single illustration in this whole log of the general pattern named in §6.4: verification code fails silently toward false confidence, repeatedly, until specifically hunted for.

1. **Import-placement bug.** The first attempt blindly prepended plain `import X` lines before the file's content. But the target file uses Lean's newer `module` / `public import ...` syntax (the same syntax first encountered earlier in this session with `Positivity/Basic.lean`). This broke parsing entirely — every single retry attempt, across all 16 residual candidates and all 14 solvers, silently failed with a parse error before ever reaching the tactic being tested. The result was reported as "still 36%, unchanged" — a completely artifactual negative finding, not a real one.
2. **Self-collision bug.** After fixing import placement, a different failure appeared: `` `inv_zpow'` has already been declared ``, repeated dozens of times. Cause: `Mathlib.Tactic.Ring`/`Abel`/`Group` themselves transitively depend on `Mathlib.Algebra.Group.Basic` — so a test file built by modifying a *copy* of that same source file, while also importing tactics that pull in the *real, unmodified* version of it, produces two independent copies of every declaration in the same environment. Fixed by abandoning whole-file copying entirely in favor of minimal, standalone per-theorem test files (goal signature + reconstructed `variable` context only) — the same technique already validated earlier in this session for the `ite_mul_one`/`Function.LeftInverse` semantic tests.
3. **Context-window truncation bug.** The minimal-file rebuild initially used a backward scan capped at 60 lines to find the governing `variable [...]` declaration. For theorems whose context was declared further back than that (confirmed case: `div_div_div_comm`'s `variable [DivisionCommMonoid α] (a b c d : α)`), the scan returned nothing, producing a malformed, context-free goal that `simp` correctly failed on for the wrong reason — not because the real tactic doesn't work, but because the reconstructed goal wasn't the real goal. This looked like a regression (three cases that had appeared to succeed in an earlier, buggier run now failed) but was actually a *more* honest result once diagnosed. Fixed by replacing the fixed-window heuristic with proper forward section-scope tracking: walking the whole file top to bottom, maintaining a real stack of open `section`/`end` blocks and the `variable` lines active within each, so every declaration gets its exact, correctly-scoped context regardless of distance.

Each of these three bugs was individually confirmed by direct inspection of the generated test file's actual content — not inferred from the pass/fail count alone — before being trusted as fixed.

### 9.3 Final, verified result

| Solver | Real closures (of 25) |
|---|---|
| `simp` | 5 |
| `aesop` | 2 |
| `ac_rfl` | 2 |
| `group` | 1 |
| **Total closed** | **10/25 = 40.0%** |

Sixteen theorems (drop to 15 after the corrected run) were not closed by any tested solver, including `mul_eq_left`, `div_div`, `inv_pow_sub`, `multiplicative_of_total`, and several `inv_mul`/`mul_inv` iff-forms — these are real candidates for what would need LLM-generated strategy (or a richer solver, e.g. ATP/SMT/hammer) in the full four-layer system.

**Comparison to the thesis's cited ~53%:** 40.0% is meaningfully lower, but the comparison is not apples-to-apples, and it would be wrong to read this as contradicting the thesis's figure. Three concrete, known differences: (1) our solver set has no ATP (Zipperposition), no SMT (cvc5), and no LeanHammer neural premise selection — the thesis's 53% is a virtual-best-solver figure across a much richer stack we have no infrastructure to run; (2) every solver call was bare and zero-argument (`simp`, not `simp [specific_lemma]`) — a real deployment would likely supply hint lemmas or a curated simp set, which materially changes `simp`'s closure rate; (3) the sample is 25 theorems from one file, not a Mathlib-wide measurement. **40.0% should be read as a real, honestly-obtained floor for the cheapest tier of Layer 0 on unfavorable, unbiased real theorems — not a benchmark result comparable to the thesis's figure, and not a refutation of it either.**

### 9.4 A second measurement: does domain matter?

The first result (§9.3) used pure group theory, where `omega`/`linarith`/`norm_num`/`positivity` are structurally irrelevant by construction — none of those goals involve inequalities or numeric computation. To get a fairer picture, we repeated the same methodology on a genuinely arithmetic/order file already built in the same environment: `Mathlib/Algebra/Order/Ring/Abs.lean` (absolute-value inequalities), with the solver list swapped to the arithmetic-appropriate set (`linarith`, `nlinarith`, `norm_num`, `positivity`, `ring`, `ring_nf`, plus the same core/general-purpose tactics as before).

The first attempt hit an immediate, honestly-diagnosed bug of a much simpler kind than §9.2's chain: the target module had never actually been built — its `.olean` didn't exist — because the file was picked by eyeballing its theorem count rather than confirming it was in the already-built dependency graph. Building it (688 jobs, mostly already-cached, ~7 seconds for the new file itself) fixed this immediately, confirmed by direct inspection before trusting the re-run.

**Result: 5/20 (25.0%) — lower than the group-theory sample, and every single success came from bare `simp`.** `omega`, `linarith`, `nlinarith`, `norm_num`, and `positivity` closed **zero** goals in their own home domain. Spot-checking a representative failure (`sq_lt_sq`, real goal `a ^ 2 < b ^ 2 ↔ |a| < |b|`) confirmed this is not a harness bug: the goal is an `iff`, and `nlinarith` correctly cannot prove a biconditional directly — it needs the goal split into its two directions first, which none of the tested solvers do automatically. Most of the arithmetic file's failures share this shape: absolute-value lemmas that require a sign case-split (positive/negative) *before* a decision procedure can close what remains, not goals the decision procedures are simply too weak for.

| Domain | Sample | Closed | Rate | Breakdown |
|---|---|---|---|---|
| Group theory (`Algebra/Group/Basic`) | 25 | 10 | 40.0% | `simp`:5, `aesop`:2, `ac_rfl`:2, `group`:1 |
| Arithmetic/order (`Algebra/Order/Ring/Abs`) | 20 | 5 | 25.0% | `simp`:5 |

This is a more useful result than either number alone: Layer 0's closure rate is **goal-shape-dependent, not just domain-dependent** — a file being "arithmetic" doesn't mean arithmetic decision procedures will close its goals if what's actually needed is a preliminary case split the procedures don't discover on their own. That's exactly the kind of "obvious first move" a proof-strategy-capable LLM would supply cheaply, which connects directly to the strategy/retrieval/bookkeeping split discussed elsewhere in this log: case-split discovery is strategy, not retrieval, and it's squarely inside what LLMs are reported to be good at.

### 9.5 Attempting the "expensive" tier: cvc5

Real progress, then a real, honestly-reported wall. `cvc5 1.3.4` (the SMT solver the original thesis's Layer 0 design calls for via QuerySMT) was downloaded directly from its GitHub release (`cvc5-Linux-x86_64-static.zip`, 43MB) and confirmed genuinely working: it correctly solved a real, hand-written `unsat` SMT-LIB problem.

Wiring it into Lean via `lean-smt` (the actual integration layer that would let cvc5 discharge real Lean goals with kernel-verified proof reconstruction) requires a specific toolchain, `leanprover/lean4:v4.32.0`, which wasn't among the three toolchains already registered this session (`v4.29.1`, `v4.32.2`, `v4.33.0-rc1`), and disk space had fallen to 1.7GB free — not enough headroom for a fourth ~3GB toolchain without risking the builds already completed. Rather than gamble a working environment on a build likely to fail partway through from disk exhaustion, this was stopped and reported honestly rather than attempted anyway. **cvc5 itself is proven to work; the Lean-side integration remains untested, blocked by disk, not by any technical or research question.**

## 10. Beyond Lean: Rocq and Isabelle

The original thesis's own survey claimed no published work applies grammar-constrained decoding to Lean, Coq, or Isabelle. Rather than take that claim at face value, we tested whether this session's methodology — build a real CFG against real, unbiased corpus text, then get a real kernel to verify real proofs — actually transfers to the other two systems, not just Lean.

### 10.1 Rocq (formerly Coq): grammar, kernel, Layer 0, and macro bridge — all four completed

**Corpus and grammar.** `math-comp` (a real, actively-used Rocq library, 147 files, 150,136 lines, cloned fresh) was extracted using Rocq's own explicit proof delimiters (`Proof.` / `Qed.` / `Defined.` / `Admitted.`) — a more reliable extraction boundary than Lean's indentation-sensitive `by`-blocks, since it's a literal textual marker rather than inferred structure. Keyword-frequency alone was strikingly concentrated: top 20 leading tokens covered 98.0% of 74,370 real tactic units, top 40 covered 99.3% — a *more* Zipfian distribution than Lean's own Mathlib measurement, consistent with SSReflect (the dominant tactic dialect in this corpus) favoring a narrow set of core tactics (`move`, `case`, `rewrite`, `have`, `apply`, `exact`) carrying rich inline modifier syntax (`//`, `/=`, view application via `/`) rather than Lean/Mathlib's broader set of many distinctly-named tactics.

A 27-production Lark CFG, built the same way as the Lean grammar (keyword dispatch, permissive `ARGS`, a recursive `bullet_tac` production for SSReflect's own `-`/`+`/`*` subgoal-focus markers — the direct structural analog of Lean's `·`), achieved **98.81% combined structural coverage on the very first pass**, before any iteration — already exceeding Lean's *first-pass* result (73.8%) and close to Lean's fully-iterated final number (99.86%). One quick, cheap fix (allowing optional trailing arguments on `split`/`right`/`left`, adding missed real tactics `field`/`auto`/`tauto`) pushed named-production coverage from 96.3% to 97.1% without changing the combined figure. The residual fallback bucket is dominated by `math-comp`'s own Hierarchy Builder (HB) structure/mixin declarations (`Build`, `pack`, `isMonoidMorphism`) — a real, domain-specific extension mechanism, correctly captured by the generic fallback rather than wrongly rejected.

**Kernel: real, working, installed differently than Lean's.** Neither GitHub Releases (Coq/Rocq doesn't publish binaries there) nor `opam` (`opam.ocaml.org` is blocked by this sandbox's egress proxy, same `host_not_allowed` response as Isabelle's site) were viable. `apt-get install coq` — reachable because `archive.ubuntu.com` is in this sandbox's allowlist — installed a real, current Ubuntu-packaged Coq 8.18.0 in one step, ~900MB. `coqc` compiled a real inductive proof (`plus_comm`) to a genuine `.vo` artifact, the direct analog of Lean's `.olean`, exit code 0.

**Discriminative semantic testing, mirroring `ite_mul_one` exactly.** On the real goal `n * 0 = 0`: `auto` genuinely passes (real proof search succeeds); `reflexivity`, `trivial`, and `simpl` genuinely fail with distinct, correct errors; `lia` and `ring` fail for an honest, structural reason — *"The reference lia was not found in the current environment"* — because they need `Require Import Lia`/`Require Import Ring` first, the exact same import-scoping behavior Lean's `linarith`/`ring` have. Confirmed `lia` works correctly once properly imported.

**Layer 0, using Rocq's own standard library (zero extra install cost — source ships alongside the compiled package).** An unbiased sample of 20 real theorems from `PeanoNat.v`, tested against `reflexivity`, `auto`, `trivial`, `lia`, `easy`, `congruence`, `constructor`, `discriminate`, `tauto`, `ring`: **8/20 (40.0%) closed with zero LLM involvement** — `reflexivity`:6, `lia`:2. This is, coincidentally, the *exact same percentage* as Lean's group-theory Layer-0 result (10/25, also 40.0%) — worth noting as a genuinely interesting data point on two unrelated systems using the same methodology, while being explicit that both samples are small (n=20, n=25) and this shouldn't be read as evidence of a deep underlying law.

**Macro bridge: completed and fully verified, five real patterns, one genuine cross-system difference found.** Rocq's `Tactic Notation` is the direct structural analog of Lean's `macro` command. All five tested patterns compiled and ran correctly, exit code 0:

```coq
Require Import Lia.
Require Import Arith.

Tactic Notation "solve_arith" := lia.
Tactic Notation "solve_auto" := auto.
Tactic Notation "combine_facts" constr(e1) constr(e2) := exact (conj e1 e2).
Tactic Notation "then_do" tactic(t) := t.
Tactic Notation "induct_on" ident(x) := induction x.

Theorem test_arith : forall n : nat, n + 0 = n.
Proof. solve_arith. Qed.

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
```

**The genuine cross-system finding**: Lean's macro bridge had a real bug this session — bare `term term` for a two-argument macro silently parsed `hp hq` as one application term rather than two arguments, requiring `term:max` to fix. Rocq's `Tactic Notation` was tested for the exact same failure mode (`combine_facts constr(e1) constr(e2)` called as `combine_facts (eq_refl 3) (eq_refl 4)`) and **does not have this problem** — it worked correctly on the first attempt. The likely reason: Rocq's argument-kind annotations (`constr(e1)`, `tactic(t)`, `ident(x)`) explicitly delimit each argument as its own grammar nonterminal occurrence, whereas Lean's bare `term` shares precedence with ordinary function-application syntax by default. This is a real, specific, useful piece of comparative design knowledge, not a restated generality — it means Rocq's macro-bridge pattern is, in this one respect, less error-prone to write than Lean's.

### 10.2 Isabelle: confirmed, hard-blocked — exhaustively checked, with one real correction along the way

Checked directly rather than assumed, across every plausible distribution channel: the official site (`isabelle.in.tum.de`), an alternate branding domain (`isabelle-prover.org`), a university mirror pattern (`www21.in.tum.de`), `apt` (no package exists at all), `snap`, `pip`, `conda-forge`, Docker Hub, GHCR, and SourceForge — all either blocked with an identical `403 host_not_allowed` response from this sandbox's egress proxy, or simply unavailable.

One genuine correction surfaced during this check, worth stating plainly rather than smoothing over: an earlier pass through this log claimed no GitHub fallback exists for Isabelle "the way it does for Lean." That was wrong. **`isabelle-prover/mirror-isabelle` is a real, reachable GitHub mirror of Isabelle's actual system distribution source** (confirmed by cloning it and reading its own README: *"The Isabelle System Distribution"*), not just the AFP theory mirror used elsewhere in this log. A source clone alone, however, doesn't get you a working Isabelle. Its own component manifest (`Admin/components/components.shasum`) lists dozens of separately-fetched, SHA-verified archives the build system depends on — Poly/ML's prebuilt binaries, JDK, Scala, jEdit, and Isabelle-specific tooling — pulled from a URL hardcoded in `etc/settings`: `ISABELLE_COMPONENT_REPOSITORY="https://isabelle.sketis.net/components"`. That exact, specific domain was tested directly rather than assumed blocked by association: **also `403 host_not_allowed`**, identical to every other path.

**The fully accurate statement, then, is more precise than the original "blocked" claim**: Isabelle's source is reachable; Isabelle's build system is not self-contained and depends on a second, equally-blocked domain for the components a build actually needs. This is a genuine, confirmed, exhaustive infrastructure boundary in this specific sandboxed environment — not a technical or research limitation, and not something left unchecked for lack of trying.

What *was* still achievable without a kernel: real grammar and extraction work. Isar's core proof language is confirmed, directly from the Isabelle/Isar reference manual's own text, to have an explicit documented grammar (*"the following grammar describes the core language (category proof)"*) — the initial framing in this log describing Isar as fundamentally less grammar-tractable than Lean/Rocq was **wrong** and was corrected mid-session. The real, sole point of difference is that Isar's outer syntax is *also* dynamically extensible via ML-registered commands, structurally the same shape as Lean 4's own parser (a documented core grammar plus dynamic extension) — not a different category requiring language redesign, which is what the MiniLang/IsaMini research direction's existence had been mistakenly read as implying.

A position-based extraction (tracking real `proof`/`qed` nesting depth, the direct analog of Lean's `by`-block indentation tracking and Rocq's `Proof.`/`Qed.` delimiters) was built against real AFP source (`Knot_Theory`, `Green`, sparse-cloned to keep disk cost to 6MB). Two real bugs, of the same category found repeatedly elsewhere in this log, were found and fixed: multi-line goal *headers* (`assumes`/`shows`/`fixes`/`and` clauses) were initially miscounted as proof-body content rather than statement signature; and quote-balance continuation merging (the direct analog of Lean's bracket-balance and colGt fixes, since Isar wraps term content in `"..."` rather than brackets) was needed to stop wrapped multi-line quoted terms from being torn into orphaned fragments. **Final result: 95.47% combined structural coverage, 26 productions, on 9,100 real, position-based proof-step lines** — lower than Lean (99.86%) and Rocq (98.81%), but for a specific, diagnosed, not-yet-fixed reason: a *third* continuation mechanism exists (fact-reference lists like `using X[of ...]` that wrap across physical lines without ever leaving a quote or bracket unbalanced), directly paralleling Lean's own colGt lesson that balance-tracking alone is insufficient and genuine indentation-awareness is also required. This is a real, cheap, well-understood next step, not an open research question.

**Summary table, three systems, same methodology:**

| | Lean 4 | Rocq | Isabelle |
|---|---|---|---|
| Grammar coverage | 99.86% (53 productions, fully iterated) | 98.81% (27 productions, one pass) | 95.47% (26 productions, two fixes, one more identified) |
| Kernel install | GitHub Releases (worked around a blocked manifest server) | `apt`, real package, ~900MB | **Blocked** — source mirror reachable, but the build's own component repository is a second, equally-blocked domain |
| Real kernel verification | ✅ | ✅ | Not attempted (blocked) |
| Discriminative semantic test | ✅ (`ite_mul_one`, 6 tactics) | ✅ (`n*0=0`, 6 tactics) | Not attempted (blocked) |
| Layer 0 measurement | 40.0% / 25.0% (two domains) | 40.0% | Not attempted (blocked) |
| Macro bridge | ✅ verified, one real bug found+fixed (`term:max`) | ✅ verified, tested for and did *not* have the analogous bug | N/A (blocked) |

---

## 11. Consolidated Findings

### 11.1 What holds up, with direct evidence

| Claim | Thesis's figure | Our measurement |
|---|---|---|
| Top-20 tactics dominate usage | ~83% (Lean4trace) | 84.9% (full Mathlib), 87% (9-file pilot) |
| CFG with ~40–60 productions covers >90% of proof steps | target | 99.86% at 53 productions, full Mathlib scale |
| Macro bridge produces real, kernel-checked proofs | design claim | Verified against real, from-source-built `positivity`/`gcongr`/`linarith` |
| Kernel gives precise, step-level diagnostics | design claim | Confirmed directly, both via raw `lean` and Pantograph's structured `"kind"` field |
| Hallucinated identifiers are a real, dominant failure mode | 47.3% (AMBER) | Directly reproduced, twice, same fabricated name (`lt_of_not_le`) |
| Layer 0 solver reconnaissance closes goals with zero LLM cost | ~53% (Mathlib-wide, VBS) | 40.0% (group theory), 25.0% (arithmetic/order) — cheapest tier only, goal-shape-dependent, see §9 |

### 11.2 What's corrected from earlier in this session

- **What was built for Pantograph was not "Mathlib" — it was Pantograph itself (44 jobs, zero Mathlib dependency) plus a compatible target environment for it to load**, which is a distinct and much larger undertaking (277+ real build jobs) forced by exact version-pinning, not by anything intrinsic to Pantograph.
- **Grammar coverage beat the thesis's own stated target** (~40–60 productions for >90% coverage) rather than merely matching it — 53 productions, 99.86%.
- **§6.6's "Internalization Theory" is withdrawn by its own author** and is excluded from anything asserted here.
- **All bugs found were in our own experimental scaffolding, never in the kernel or Pantograph**, both of which performed correctly every time they were used directly — a fact initially conflated in this log and explicitly corrected mid-session.

### 11.3 What remains genuinely untested

- **Layer 0's expensive tier, partially attempted.** `cvc5` itself was installed and confirmed working (solved a real SMT-LIB problem correctly). Its Lean-side integration (`lean-smt`) remains untested — blocked by a toolchain we don't have registered plus 1.7GB free disk, not by a technical or research obstacle. ATP (Zipperposition via Lean-Auto) and LeanHammer's neural premise selection were not attempted at all.
- **Layer 3 (the training flywheel)** — entirely unbuilt, unmeasured, theoretical in both the original document and here.
- **A true closed loop** — live model generation and kernel verification automatically driving each other, with no human relay — was never achieved in this sandbox, because bash had no API credentials and the browser artifact environment has no Lean kernel. Every kernel check on real LLM output this session involved a human copying text between the two.
- **Any head-to-head number** — constrained vs. unconstrained, at any Pass@K, on any benchmark — was never produced. Everything here is existence evidence (specific failure modes happen, specific fixes work), not benchmark evidence (how often, at what scale, compared to what baseline).

---

## 12. Where This Leaves Things

The syntax-and-hallucination half of the original error taxonomy — 4.8% + 47.3% ≈ 52% of the AMBER benchmark's error mass — now has real, hands-on evidence behind a credible mitigation path: grammar handles the former essentially completely (99.86%, cross-validated three ways), and kernel/Pantograph handles the latter with native precision that exceeds what an ad hoc checking layer can achieve, confirmed by direct comparison. Neither claim rests on the original thesis's citations alone anymore; both were independently produced and, in the grammar's case, exceeded the thesis's own stated target.

The other half of the taxonomy — misapplied tactics (32.7%) and incomplete outputs (15.2%) — is proof-*strategy* failure, and nothing built or tested this session fully addresses it. Layer 0's cheap tier (§9) gives a first real, if partial, measurement here: 40.0% on group theory and 25.0% on arithmetic/order, both meaningfully below the thesis's cited 53%, for well-understood, honestly-attributed reasons (no ATP/SMT/hammer, no hint lemmas, small single-file samples). The arithmetic result is the more interesting of the two: it shows Layer 0's ceiling is **goal-shape-dependent, not just domain-dependent** — decision procedures close inequalities that are already case-split, not the case split itself, and most of the arithmetic file's failures needed exactly that missing first move. That's a concrete, testable hypothesis for anyone continuing this work: try a case-split preprocessing pass (`rcases abs_cases`, `rcases le_or_lt`, etc.) ahead of the decision procedures on the same residual goals, rather than adding yet more solvers of the same kind.

The single most transferable lesson, independent of Lean or theorem proving specifically: **verification-layer code built to check an untrusted generator's output needs to be tested as adversarially as the generator itself.** Every bug found this session — the 4x dependency-closure overestimate, the swallowed API error, the namespace-blind identifier match, and now the three-bug chain in the Layer 0 experiment itself (broken import syntax silently failing every retry, a self-collision from whole-file copying, a context-window truncation producing malformed goals that failed for the wrong reason) — failed in the same direction: toward false confidence, not false alarm. The Layer 0 experiment is the clearest single demonstration of this in the whole log: each bug individually produced a plausible-looking, wrong number, and each was only caught by directly inspecting the generated test file's actual content rather than trusting the pass/fail count. That's the natural failure mode for any checking layer, because a bug that silently approves bad output is invisible until specifically hunted for, while a bug that raises false alarms gets noticed immediately by an annoyed user. Anyone building further on this should budget real effort for testing the checkers, not just the thing being checked — and should expect to need more than one round of adversarial testing before trusting a number, even from careful-looking code.
