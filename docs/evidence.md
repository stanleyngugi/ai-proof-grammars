# Article claim-to-evidence map

Reanalysis date: 2026-09-05. No new GPU generation or theorem-proving benchmark.
Commands below run from the companion repository root after installing
`requirements-analysis.txt`. See `provenance.md` for historical/recovered inputs.

| Claim or illustration | Evidence | Reproduction | Scope |
|---|---|---|---|
| Qwen 420/640 vs 640/640 accepted | `analysis/audit.json`, `runs.*qwen.classification_counts` | `python analysis/audit.py` | First cleaned line; permissive CFG |
| Keywords 385 vs 584; flags 319 vs 339 | Same JSON; `known_leading_keyword`, `identifier_flagged` | Same command; independent CSV via `python post2-constrained-decoding/score.py qwen` | Historical vocabulary/name heuristics |
| Sorry/admit 2 vs 16 | `sorry_or_admit` | Same | Lexical flags, not proof-dependency checks |
| Diversity 7.10 vs 7.00 | `mean_distinct_strings_per_goal` | Same | Distinct text, not strategies |
| Latencies .30353125 vs .347296875 | `mean_latency_s` from raw recorded request durations | Same | Observational means, no isolated causal overhead |
| Zero Qwen ablation disagreements | `reduced_grammar_disagreements` and `analysis/audit.py:REDUCED` | Same; regression test | Finite 1,280-output comparison, not universal equivalence |
| CFG accepts `rw [`, `exact (`, prose | `counterexamples` and tests | `python -m unittest discover -s tests` | Executed against historical scoring grammar |
| Strict teaching grammar requires brackets | `test_strict_teaching_grammar_checks_brackets` | Same | Deliberately incomplete supported subset |
| Extractor flattens constructor/bullets | `test_extraction_limitation_remains_visible` | Same | Limitation of historical extractor, not proposed Lean semantics |
| Goal `card_pow_le` contains extra source | `data/goals.jsonl`, id 6556 | Inspect raw row | Dataset limitation; not repaired silently |
| Revised mutation 219/6413 | `analysis/strength.json` | `python post1-tactic-cfg/strength_analysis.py --mathlib /path/to/pinned/mathlib` | Seed 42; specified corpus and class mixture |
| Historical corpus 143949/144154 accepted | `docs/historical/research-log.md` §3.3 | Initial exact run not reconstructable from committed inputs | Reported history; no corpus-wide syntax guarantee |
| Historical Rocq/Isar percentages | Historical log §10 | Not rerun in this revision | Distinct heuristic units; exploratory observations |
| Native Goedel first lines 130/139 vs selected-line 49.9% | `audit.json` native run classifications + line_accounting | Audit or `yield_analysis.py` | Different denominators on same file |
| Goedel constrained recovered denominator 640 | Recovered JSONL and audit | Audit | Enforcement not established |
| Raw output examples with IDs | `analysis/examples.json` | Audit | Hand-selected illustrations, not representative sample |
| Numerical mask example | Arithmetic .5/.7 and .2/.7 | Direct calculation | Hypothetical teaching probabilities, not recorded logits |

## Reanalysis records

`audit.json` hashes raw data, both grammar sources, and analysis implementation.
`strength.json` records corpus commit, RNG seed, script/extractor hashes, and
prose-input hashes. Counts are stored unrounded. Figures are generated from these
JSON files with `analysis/figures.py`; SVGs are committed as standalone artifacts.
Original score CSVs remain untouched by the corrected scorer.

The historical corpus checkout/source output is incomplete as a provenance chain.
That is why old counts remain labelled historical instead of being described as
newly validated. The later mutation run does not supply an independent extraction
oracle: it uses the same heuristic whose limitation the first article demonstrates.

## Primary sources used for technical context

- Lean tactic syntax, macros, and elaboration:
  https://lean-lang.org/doc/reference/latest/Tactic-Proofs/Custom-Tactics/
- llguidance implementation/documentation: https://github.com/guidance-ai/llguidance
- CRANE and optional reasoning before constrained output: https://arxiv.org/abs/2502.09061
- Goedel-Prover-V2: https://arxiv.org/abs/2508.03613
- GRPO: https://arxiv.org/html/2402.03300v3
- Earlier grammar-based tactic generation (distinct architecture):
  https://proceedings.mlr.press/v97/yang19a/yang19a.pdf
- Lean4trace, extraction through Lean: https://openreview.net/forum?id=sjLWmLeJ6R
- Related public LeanGCD project, not evidence of a completed result:
  https://ai.math.uw.edu/projects/spring-2026/

These sources contextualize the experiment. Their benchmark scores and theoretical
results are not imported as evidence for this project's measured outcomes.
