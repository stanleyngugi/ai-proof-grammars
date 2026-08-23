# Grammar-Constrained Decoding for Lean 4 Tactics

Companion code for a research blog series on measuring — and then using —
grammar constraints for LLM-driven Lean 4 theorem proving.

**Posts**
1. [Lean's Tactic Language Is Smaller Than It Looks](https://stanleyngugi.netlify.app/posts/2026-08-22-lean-tactic-language-cfg)
   → `post1-tactic-cfg/`
2. [A Quarter of Your Prover's Tokens Never Reach the Judge](https://stanleyngugi.netlify.app/posts/2026-08-22-grammar-constrained-decoding-lean)
   → `post2-constrained-decoding/`

## Structure

```
data/                            shared artifacts (sampled goals, keyword
                                 frequencies, 163k-declaration name table)
post1-tactic-cfg/
  lean_experiments.py            consolidated original experiment code:
                                 extraction (colGt-aware continuation
                                 merging), the 53-production CFG, name
                                 extraction, hallucination checker,
                                 Layer-0 harness, macro bridges
  grammar_report.py              the CFG as a module
  prep_data.py                   rebuild data/ from a mathlib4 clone
  strength_analysis.py           mutation battery measuring constraint
                                 STRENGTH (the number post 1 declines to
                                 claim; addendum: ~3.5% overall rejection)
post2-constrained-decoding/
  gen_eval.py                    unconstrained vs grammar-constrained
                                 generation via vLLM + llguidance
  score.py                       CFG-validity / keyword / hallucination
                                 scoring
  yield_analysis.py              kernel-reachable line-yield accounting
  hardened_generate.py           reserved-token enforcement wrapper
                                 (generate -> validate -> resample)
  results/                       raw generations + score CSVs
pantograph-harness/
  kernel_loop.py                 closed-loop client for the Pantograph
                                 REPL with per-step feedback taxonomy
  ite_mul_one_replay.py          end-to-end proof replay against a real
                                 Mathlib environment
```

## Reproducing

```bash
pip install -r requirements.txt

# post 1 (CPU only): needs shallow clones of mathlib4 + batteries next to repo root
python3 post1-tactic-cfg/prep_data.py
python3 post1-tactic-cfg/strength_analysis.py

# post 2: needs a CUDA GPU + vLLM serving one of the models
python3 -m vllm serve <model-dir> --served-model-name m \
  --max-model-len 4096 --gpu-memory-utilization 0.92 --enforce-eager \
  --guided-decoding-backend guidance
python3 post2-constrained-decoding/gen_eval.py --cond unconstrained --tag run1
python3 post2-constrained-decoding/gen_eval.py --cond constrained --tag run1
python3 post2-constrained-decoding/score.py run1
```

## Pins & known gotchas (these will bite you otherwise)

- `vllm==0.10.2` — newer engines had issues on our stack; also flashinfer
  must be uninstalled (`array.array` annotation crash at import).
- **vLLM silently drops grammar enforcement under parallel sampling
  (`n > 1`) and can fall back to unconstrained decoding on per-request
  backend errors.** Request `n=1`, pin the backend server-side
  (`--guided-decoding-backend guidance`), and assert enforcement post-hoc.
- Pantograph version-pins Lean exactly; this series used Pantograph commit
  `c6136e8` (Lean v4.23.0) with Mathlib tag `v4.23.0`.
- Launch the REPL *with import arguments* (`repl Init ...`) — bare launch
  yields an empty environment where even core notation fails to parse.

## License

MIT (see LICENSE). Mathlib/Batteries-derived artifacts retain their
upstream Apache-2.0/MIT licensing with attribution.
