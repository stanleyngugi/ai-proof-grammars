# Validation — September 5, 2026

The staged companion tree was exported to a clean temporary checkout. Its ten
regression tests passed with Python 3.12.3 and Lark 1.3.1. Tests cover actual CFG
counterexamples, the reduced-grammar comparison on all 1,280 Qwen outputs, the
strict teaching grammar, historical extraction/cleanup limitations, correct line
and mutation denominators, bounded retries, and sample-level resume handling.

The raw-output audit was rerun in that clean checkout; its committed hashes refer
to the repository files, independent of pre-existing local line-ending edits.
The independent Qwen scorer and selected-line analysis reproduced the article
counts. The later Mathlib mutation rerun reproduced 219/6,413 rejected candidates;
see strength.json for revision, seed, hashes, and class denominators.

Four SVGs were generated with matplotlib 3.10.5 and explicit SVG diagrams.
Website synchronization and a byte-identical rebuild passed, as did local link,
anchor, source-hash, metadata, and XML checks. Chromium reviewed both articles at
390px and 1280px in both themes: all images loaded, TOC links navigated, and no
page overflow or JavaScript/HTTP errors remained. Website review records are in
its docs/ directory.

No GPU generation, new Lean execution benchmark, or Pantograph repair was part
of this revision. Historical reports/proposals and generated SVGs intentionally
retain their original/generated whitespace; authored code and prose were checked
for whitespace errors separately. Regenerated CSVs are reproducible local outputs
and ignored by Git; original historical CSVs remain tracked and preserved.
