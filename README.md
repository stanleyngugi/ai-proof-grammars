# Lean tactic grammars and constrained generation

Companion code and evidence for two technical articles:

1. [Building a Grammar for Lean Tactics: Coverage, Structure, and Constraint Strength](articles/01-tactic-cfg.md)
2. [Grammar-Constrained Decoding for Lean Tactics: An Experiment with vLLM and llguidance](articles/02-constrained-decoding.md)

The September 2026 revision distinguishes **acceptance by a permissive CFG** from
Lean syntax validity and proof success. The saved Qwen result reproduces: 420/640
first cleaned lines accepted without the configured constraint, 640/640 with it.
This repository does not claim measured kernel contact, token savings, or training
improvement from those counts.

## Reproduce saved-output analysis (CPU only)

Python 3.10+ is required; validated with Python 3.12 and Lark 1.3.1.

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements-analysis.txt
python analysis/audit.py
python post2-constrained-decoding/score.py qwen
python post2-constrained-decoding/yield_analysis.py
python -m unittest discover -s tests -v
```

No model downloads, GPU, Lean installation, or API key are needed. Raw JSONL files
and original score CSVs remain under `post2-constrained-decoding/results/`.
Regenerated scores and summaries go to `analysis/`, including an input-hash
manifest, exact denominators, examples with sample IDs, and the reduced-grammar
ablation. [Evidence map](docs/evidence.md) · [Provenance](docs/provenance.md).

## Mutation sensitivity

```bash
python post1-tactic-cfg/strength_analysis.py \
  --mathlib /path/to/mathlib4 --out analysis/strength.json
```

The committed rerun uses Mathlib revision
`53c82c1c23ec418ebf7290390bc8108957bef853`, seed 42, and 5,000 sampled entries.
This command uses the **historical heuristic extractor**, whose over-merging is
illustrated and tested. Its entries are not validated individual Lean tactic
applications. Do not compare different corpus revisions as identical runs.

To rebuild heuristic input tables, choose a separate output directory:

```bash
python post1-tactic-cfg/prep_data.py --mathlib /path/to/mathlib4 \
  --batteries /path/to/batteries --out /tmp/new-cfg-inputs -n 80
```

Do not overwrite the committed inputs when reproducing the published saved-output
analysis. The historical goal sampler can include malformed/missing-context
statements; it is retained for provenance, not recommended as a validated benchmark.

## Figures

```bash
pip install -r requirements-figures.txt
python analysis/figures.py
```

This creates four standalone SVG illustrations under `articles/assets/`.
The statistical plots read committed analysis outputs. Conceptual diagrams are
explicit illustrations, not model traces. Website rendering instructions live in
the website repository; the Markdown articles here are the canonical sources.

## Historical generation

`gen_eval.py` retains the vLLM 0.10.2 request configuration, with sample-level resume
tracking repaired. `requirements.txt` is the historical serving requirements
file, separate from the lightweight analysis dependencies. A compatible served
model and GPU environment are needed for new generations. This revision did not
rerun GPU generation or establish a general backend bug.

`grammar_lean.lark` is the generation language; `grammar_report.py` is the scoring
language. They differ. The generic alternative admits prose and omitted words
such as `sorry`; acceptance does not certify Lean syntax or admissions policy.
The optional `hardened_generate.py` wrapper is a bounded lexical retry policy,
not a proof checker. Always validate enforcement with the exact generation
language and retain request configuration and termination information.

## Scope separation

Pantograph, solver orchestration, and later model/proof-state work were moved to
the sibling `lean-proving-experiments` project. Their historical paths contain
pointers, and their source remains in Git history at `a147ec9`. That future project
preserves proposals, ideas, original code, and known evaluator bugs. It is deferred
while these two articles and their evidence are the publication focus.

## License

MIT for the project code (see LICENSE). Mathlib and Batteries derived material
retains its upstream licensing: see [Mathlib](https://github.com/leanprover-community/mathlib4)
and [Batteries](https://github.com/leanprover-community/batteries). The source-derived
artifacts are included to make the experiment inspectable, with their extraction
limitations documented rather than presented as an authoritative Lean environment.
