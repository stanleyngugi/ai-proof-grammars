# Editorial memory for the two deep redrafts

Saved 2026-09-05. The user resumed implementation after the initial deep-redraft
pause. Both expanded articles now have evidence-backed examples, figures, and
local website integration. They are ready for editorial review, not yet merged
into the live website. Pantograph remains deferred. No subagents were used.

## Intent to preserve

The user wants long, technically substantial articles with worked examples,
mechanism, experimental detail, and code illustrations. The original proposals
predate the experiments; treat them as exploratory intellectual history, not as
material for a prolonged critique. Correct unsupported published claims without
turning either article into a bug report or apology. Pantograph is a separate,
deferred project, not the prerequisite or main subject of these two posts.

Draft 1 develops the grammar as a classifier, accepted language, and possible
designed action interface. Draft 2 explains masking, token boundaries, the exact
saved experiment, scoring choices, observed outcomes, and optional reasoning.
Together they should let a reader reconstruct the experiment and understand why
the design is interesting even where the original interpretation was too broad.

## Source map: original proposals to article material

The full originals have been preserved in
`../../lean-proving-experiments/original-proposals/`.

| Original source | Idea to retain | Treatment in redrafts |
|---|---|---|
| BLUEPRINT §1, §3 | Structure supplied at inference time; separate roles of generator and formal machinery | Short motivation; do not import whole-system guarantees |
| BLUEPRINT §2; LEAN CONTEXT §5.1 | Constrain the result after optional free reasoning | Draft 2 explains A/B architectures; historical experiment tested direct generation only |
| BLUEPRINT §4.1, §10.3 | Triggered switching between output modes | Draft 2 preserves hypothesis and tokenizer-boundary requirement; no claim it was implemented |
| BLUEPRINT §4.2, §10.2 | Token/character misalignment and logit masks | Worked prefix example, mask formula, labelled pseudocode |
| BLUEPRINT §4.3–4.5; LEAN CONTEXT §4.4 | Runtime representation and caching | Brief mechanism; detailed engine benchmarking belongs to later work, not invented measurements |
| LEAN CONTEXT §4.1 | Compact tactic vocabulary and extensible Lean syntax | Draft 1 motivates a supported subset without equating it to the full parser |
| LEAN CONTEXT §4.1.1 | Macro bridge and a controlled output language | Draft 1 has a substantive constructive section on interface design and its tradeoffs |
| LEAN CONTEXT §4.3, §10.1 | Explicit structure versus permissive TERM | Compare proposed rewrite/list/location structure with actual ARGS catch-all |
| BLUEPRINT §11; LEAN CONTEXT §12 | Explicit metrics and efficiency | Draft 2 defines measured units and separates future token/proof metrics |
| Both documents' solver/training sections | Automation, proof-state loops, solver traces | Saved in separate project's ROADMAP; not inserted into these posts |

The initial LEAN CONTEXT grammar was substantially more structured than the
actual scoring grammar. Do not repeat the old blog's claim that the proposal
sketched exactly the implemented KEYWORD/ARGS language. Explain the evolution.

## Evidence already established

`../analysis/audit.json` is regenerated from saved raw outputs. No GPU rerun.

- Qwen unconstrained: 640 samples/80 goals, 388 named + 32 fallback = 420 accepted.
- Qwen constrained: 640/80, 592 named + 48 fallback = 640 accepted.
- Known keyword counts: 385 versus 584. Identifier-flag counts: 319 versus 339.
- Sorry/admit string flags: 2 versus 16. Distinct strings per goal: 7.10/7.00.
- Mean latency: 0.30353125 versus 0.347296875 seconds; approximately 14.4% higher
  observed constrained mean. Not an isolated causal engine-overhead estimate.
- Reduced grammar (fallback + focus + case arms): zero acceptance disagreements
  on the 1,280 Qwen outputs. Finite comparison, not universal language equivalence.
- Native Goedel: 139 samples/69 goals; 130 accepted first cleaned lines. The
  historical line selector retains 1,970 lines, approximately 49.9% accepted.
- Recovered constrained Goedel: 640/80; 541 first lines accepted. Existing score
  CSV had only 589 scored samples. Do not mix those denominators.
- Counterexamples accepted by scoring CFG: English prose, `rw [`, `exact (`,
  `sorry`, `rfl nonsense`, and a made-up name inside simp arguments.
- Historical extractor flattens a constructor/two-bullet proof into one entry.
- Original data goal `card_pow_le` includes proof branches and later declaration.

## Additional result completed while drafting

The repaired mutation script completed on the later local Mathlib checkout
`53c82c1c23ec418ebf7290390bc8108957bef853`, using the historical heuristic extractor.
It found 8,373 Mathlib-subtree files and 145,168 extracted entries. This is not the
initial report's corpus and must not replace its counts silently.

Sample: 5,000 real entries, 9 rejected (0.18%). Corrected combined corruption
denominator: 6,413 (includes 1,630 harvested prose examples). Approximately 3.4%
rejected overall, 4.5% under the additional lexical policy. Per-class counts are
in `../analysis/strength.json`; use exact values there, not rounded prose.
English-lead and prose acceptance remain extremely permissive. This run is included as a clearly dated reanalysis in article 1, with a
class-by-class table and figure.

## Completed implementation pass

- Added the actual saved model examples with IDs, numerical masking walkthrough,
  reduced-grammar comparison, and dated mutation results.
- Generated four SVGs: extraction, decoding, Qwen acceptance, and mutation rejection.
- Added lightweight pinned analysis/figure dependencies and ten regression tests.
- Reproduced raw-output audit, independent scorer, selected-line accounting, and
  the mutation run; no GPU/API or new theorem-proving experiment.
- Integrated articles in the website with synchronized Markdown, build script,
  navigation, syntax highlighting, responsive figures/tables, revision archives,
  original URLs/dates, and updated homepage/RSS/citation metadata.
- Added website integrity checks and desktop/mobile browser review in both themes.

## Remaining editorial choices

Read both articles for voice and emphasis. Their technical evidence is prepared;
publication still deserves an author pass. Keep the constructive language-design
sections central, avoid turning the narrative into correction history, and retain
exact definitions wherever claims depend on cleanup or extraction.

Future experiments are recorded in the separate project's ROADMAP.md. They are
ideas to select among, not prerequisites to reviewing these two articles.

## Publication policy

Preserve the original dates/URLs, add a dated revision note, and archive old
publication text. Change titles/descriptions in homepage, RSS, and metadata
consistently. Do not publish deep working drafts or push directly to the website's
deployment branch. No changes have been published in this session.
