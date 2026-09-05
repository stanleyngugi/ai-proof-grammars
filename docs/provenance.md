# Scope, provenance, and revision policy

Revision date: 2026-09-05. This repository supports two articles about a Lean
tactic CFG and constrained generation. Proof search, Pantograph development,
solver orchestration, and training are deferred to the sibling local project
`../lean-proving-experiments`. Original harness sources remain in Git history at
`a147ec9`; directory READMEs preserve discoverability of the old paths.

## Historical artifacts

- `data/goals.jsonl`, `names.json`, and `kw_freq.json` are preserved inputs.
  The goal set is a heuristic extraction, not a validated collection of standalone
  statements. For example, goal `card_pow_le` includes later source text.
- `post1-tactic-cfg/lean_experiments.py` remains the original consolidated code.
  Its extraction merges some complete multi-step proofs into single entries.
  Its comments and reported historical results are not revised findings.
- `grammar_report.py` is the historical post-hoc scoring language. The
  `grammar_lean.lark` generation language is different. Header comments were
  corrected, without changing that generation language.
- Original score CSVs are preserved. Corrected scoring writes to `analysis/`.
- `constrained__goedel.jsonl` and `unconstrained__goedel.jsonl` were recovered
  from the local `gcd_exp/results` directory. Their recovery does not establish
  successful masking. The native generator is retained as `native_run_legacy.py`
  for configuration provenance, not as the recommended driver.
- The native Goedel file contains 139 generations on 69 goals. The recovered
  first-step files each contain 640 generations on 80 goals. Historical Goedel
  score CSVs need not describe the complete recovered files.

The initial 144,154-entry/99.86% corpus figures are recorded in the original
research report, but an immutable initial corpus commit and extraction output
are not present in the companion repository. They are historical observations,
not a newly reproduced estimate of all Lean tactic usage. The nearby later
Mathlib checkout has commit `53c82c1c23ec418ebf7290390bc8108957bef853`;
it must not be silently substituted for the initial corpus.

## What the revised analysis establishes

`analysis/audit.py` reads saved generations, recomputes CFG acceptance and
heuristic name flags, compares the reduced grammar, and records hashes and exact
denominators. It does not run Lean or establish theorem-proving performance.
`strength_analysis.py` is repaired to report every class denominator and handle
empty inputs; its source extraction remains explicitly labelled historical.

The blog drafts are maintained in `articles/`. The website uses the original
post URLs with a dated revision note. Original publication text is archived
before replacement. No historical data is overwritten to make a new narrative.
