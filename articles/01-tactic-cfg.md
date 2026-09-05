# The Shape of a Lean Tactic

*What a small grammar captures, what its fallback gives away, and how to measure the difference.*

> **Updated September 5, 2026.** Expanded from the August 22 article with executable examples, a grammar ablation, and explicit measurement definitions. The original corpus figures are retained as historical observations, with their extraction limitations explained below. [Original version](/archive/revisions/2026-08-22-lean-tactic-language-cfg-original.html) · [Evidence and reproduction](https://github.com/stanleyngugi/tactic-grammar-lab/blob/main/docs/evidence.md).

A grammar for Lean tactics begins with an attractive observation. Many proof steps start with a familiar word: `rw`, `simp`, `exact`, `apply`, `intro`. Behind a large mathematical library there appears to be a comparatively small vocabulary of actions. If a language model repeatedly uses those actions, perhaps a compact grammar can guide its generation without representing the entirety of Lean.

The interesting work begins when we ask what “representing a tactic” means. Consider three lines:

```lean
rw [mul_comm]
simp only [h₁, h₂] at h
exact f x
```

Recognizing their leading words is easy. Checking that the rewrite list closes, that `at` has an appropriate location, and that the term after `exact` is syntactically well formed is a different task. Determining whether `f x` proves the current goal is another task again.

I built a small Lark grammar, extracted tactic-like text from Mathlib, and measured how often the grammar accepted that text. The original report recorded 99.86% acceptance on 144,154 extracted entries. That was an encouraging corpus-fit result. Subsequent inspection showed why it cannot stand alone: the grammar is permissive, the extraction has structural limitations, and an English sentence can receive the same acceptance verdict as a real tactic.

The central question is what we want the grammar to do: label familiar syntax, exclude unwanted outputs, or define an interface for a model. Those jobs can share code while requiring different evaluations. This article develops the distinctions with the actual grammar and examples. The [companion experiment](/posts/2026-08-22-grammar-constrained-decoding-lean.html) examines what happened when a related grammar was used during model generation. Together they study a particular representation and its effects; they do not establish a complete theorem prover.

## A useful subset is a design decision

Lean lets users extend syntax and implement new tactics. A fixed grammar written outside Lean therefore needs an explicit scope: a particular environment, a supported collection of forms, or an approximation that tolerates unfamiliar extensions. The existence of extensions does not mean we must model every extension before doing useful work. It means we must explain what our grammar promises.

Lean’s parser architecture and syntax categories provide useful guidance, but reproducing a keyword dispatch pattern is not the same as reproducing Lean’s parser. Its tactic syntax can contain terms, nested tactic sequences, notation, and layout-sensitive constructs. The [Lean reference manual](https://lean-lang.org/doc/reference/latest/Tactic-Proofs/Custom-Tactics/) explains how tactic syntax and its implementation connect to the elaborator.

For this project, the initial practical choice was a keyword-oriented approximation. Frequently observed forms received named alternatives. Argument text was mostly left unrestricted. Unknown identifier-led forms received a generic fallback so unfamiliar macros would not immediately count as failures.

That design serves two purposes which must be evaluated separately. As a classifier, it can label common surface forms. As a decoding constraint, it defines which strings a model may produce. A helpful classification hierarchy is not necessarily a restrictive language.

There is also a difference between the original architectural proposal and the implemented experiment. The proposal sketched explicit rewrite lists, simplifier arguments, locations, and control constructs. The experimental grammar delegated much more content to a catch-all. The experiment consequently tests a broader approximation than that more structured proposal suggested.

## Read the grammar before reading the percentage

Here is a shortened version of the actual scoring design. The full file contains 53 named tactic alternatives, including the focus and case-arm forms, plus the generic fallback. “53” counts those alternatives; it is not a count of every grammar definition and lexical terminal.

```lark
start: tactic

tactic: rw_tac
      | exact_tac
      | rfl_tac
      | generic_tac

rw_tac.2: "rw"i ARGS
exact_tac.2: "exact"i ARGS
rfl_tac.2: "rfl"i

generic_tac.-1: IDENT ARGS?
IDENT: /[A-Za-z_][A-Za-z0-9_'!]*/
ARGS: /.+/

%import common.WS
%ignore WS
```

The suffixes `.2` and `.-1` influence rule preference in Lark’s interpretation. The `i` makes these quoted literals case-insensitive. Both details matter: this is a grammar for classification, with deliberate behaviour that should not be confused with Lean’s own case-sensitive syntax.

`rw_tac` demands the literal and some argument text, but it does not demand a bracketed list. `ARGS` accepts an arbitrary nonempty run matched by its regular expression. It has no production describing a matching closing bracket. Likewise, `exact_tac` does not parse an application tree for `f x`; it consumes the remaining text.

The generic rule is even more consequential. Suppose `rfl nonsense` does not match the fixed `rfl_tac` alternative. It can still match `generic_tac`: an identifier followed by argument text. Putting the fallback at lower priority changes which successful parse is preferred. It does not make the fallback unavailable when a named form rejects a string.

That explains these executable counterexamples:

| Input | Historical scoring classification | What the classification misses |
|---|---|---|
| `rw [` | Named: rewrite form | Unclosed argument list |
| `exact (` | Named: exact form | Incomplete term |
| `rfl nonsense` | Generic fallback | A fixed tactic’s argument restriction |
| `sorry` | Generic fallback | An omitted keyword is still admitted |
| `The first step is to induct on the structure of n.` | Generic fallback | English prose begins with an identifier |

These are not hypothetical problems in a different grammar. They are acceptance results from the companion code. Nor does calling the grammar a “category gate” resolve the issue: it accepts text outside the intended category too.

The useful conclusion is narrower. The grammar recognizes a broad family of identifier-led surface forms, with additional support for a small amount of structure. Whether that bias is helpful during generation is an empirical question for the second article.

## What explicit structure buys

To see the tradeoff, replace the broad rewrite rule with a deliberately small grammar:

```lark
start: rw_tac
rw_tac: "rw" "[" name ("," name)* "]"
name: /[A-Za-z_][A-Za-z0-9_'.]*/
%import common.WS
%ignore WS
```

This teaching grammar accepts `rw [mul_comm]` and `rw [h1, h2]`. It rejects `rw [` because the list must close. It also rejects valid Lean forms outside its support, such as a reverse rewrite using `←` or a more elaborate term. That is a scope decision we can see directly in the productions.

Adding a `generic_tac` alternative would weaken that guarantee again. The accepted language is the union of the alternatives. A string rejected along one path can survive along another. Consequently, the questions to ask when adding a fallback are: what valid examples does it recover, and what invalid examples does it re-admit?

There is no need to claim that all term syntax is impossible to model with a grammar in order to justify a restricted experiment. Many useful pieces—lists, delimiters, optional clauses, bounded argument forms—can be represented explicitly. Resolving names and checking types are separate matters. A dictionary of candidate names can restrict spellings without proving that a chosen name applies to the current goal.

The engineering tradeoff is between expressiveness, precision, and maintenance. A broad slot supports more existing text with fewer rules. A structured slot supplies more checks but needs additional productions and careful treatment of valid syntax. Neither choice should be evaluated using coverage alone.

## Remove the named rules and measure again

The catch-all suggests a simple ablation. Keep only the generic identifier-led rule and the two explicitly modelled structural forms. Does acceptance change on the saved model outputs?

```lark
start: tactic
?tactic: generic_tac | focus_tac | case_arm_tac

generic_tac: IDENT ARGS?
focus_tac: "·" tactic
case_arm_tac: "|" CASE_PATTERN "=>" tactic?
```

The lexical rules are kept consistent with the historical scoring grammar. I ran both parsers on the first cleaned line of every saved Qwen output—the same unit used in the original Qwen score table.

| Saved outputs | Full scoring grammar | Reduced grammar | Disagreements |
|---|---:|---:|---:|
| Unconstrained Qwen | 420/640 accepted | 420/640 accepted | 0 |
| Constrained Qwen | 640/640 accepted | 640/640 accepted | 0 |

This is a finite comparison, not a proof that the grammars accept exactly the same language. It also says nothing yet about compilation cost or generation speed. Its conclusion is concrete: on these 1,280 outputs, the named alternatives change the available labels without changing acceptance decisions.

The result helps explain why a large named-match percentage can coexist with weak rejection. A parser can attach a specific label to `rw [` even though the accepted language is permissive enough to admit the same text without that named alternative.

It also suggests a useful research direction: compare grammar representations while holding their language fixed, and compare accepted languages while holding other implementation choices fixed. Otherwise a change in rule count mixes classification, expressiveness, and runtime representation in one number.

## Two measurements, with two denominators

For a reference collection of extracted entries, corpus acceptance is:

```text
coverage = accepted reference entries / tested reference entries
```

For a specified corruption experiment, rejection is:

```text
rejection rate = rejected mutated entries / tested mutated entries
```

A grammar that accepts every string gets perfect coverage and rejects nothing. High coverage is therefore not sufficient evidence that a decoder constraint eliminates malformed output. Conversely, an aggressively restricted grammar may reject many malformed strings while also excluding useful tactics.

The denominator is part of the measurement. Reference entries could be physical lines, logical tactic applications, complete proof blocks, or distinct strings. Those are different populations. A proof containing repeated `simp` calls contributes differently to a frequency-weighted corpus measure and a deduplicated measure.

For the corruption experiment, the mixture matters just as much. Truncation, prose replacement, argument shuffling, and random identifier sequences probe different behaviours. Changing their proportions changes the aggregate. Some mutations also remain valid Lean: swapping one real keyword for another is not a ground-truth test of syntactic invalidity. It measures sensitivity to that replacement.

The revised mutation run makes those denominators explicit. It sampled 5,000 entries from a later Mathlib checkout, retaining the historical heuristic extractor. Nine untouched entries were rejected. Each entry received one randomly chosen mutation; unchanged mutations were excluded. A separate pool contributed 1,630 candidate prose lines harvested from saved Goedel outputs. That pool is selected by textual heuristics, not human-labelled ground truth.

| Mutation or candidate class | Rejected / tested | Rejected |
|---|---:|---:|
| Truncation | 1 / 854 | 0.12% |
| English-word lead | 0 / 824 | 0% |
| Different real tactic keyword | 0 / 795 | 0% |
| Argument shuffle | 1 / 725 | 0.14% |
| Full token shuffle | 217 / 741 | 29.28% |
| Identifier soup | 0 / 844 | 0% |
| Harvested prose candidates | 0 / 1,630 | 0% |
| Combined | 219 / 6,413 | 3.41% |

<figure>
<img src="/assets/cfg/mutation-rejection.svg" width="820" height="480" alt="Full token shuffle rejects 217 of 741 examples; truncation and argument shuffle reject one each; the remaining four classes reject zero." loading="lazy">
<figcaption>Rejection depends strongly on the mutation class. Counts and the historical extraction procedure are part of the result.</figcaption>
</figure>

Most rejection comes from shuffling the entire string, which can move punctuation into the leading position. Replacing a keyword with an English word leaves the broad identifier-led shape intact. That pattern is consistent with the grammar rules we inspected, and it is more informative than the aggregate alone.

This dated rerun used Mathlib commit `53c82c1c23ec418ebf7290390bc8108957bef853`: 8,373 files under its Mathlib subtree and 145,168 extracted entries. It is not a reconstruction of the initial corpus. The original addendum’s 3.5% also came from different accounting: its combined numerator omitted prose rejections while its denominator included prose. The revised script and provenance record make both the class mixture and the calculation inspectable.

## Extracting the corpus is part of the experiment

The initial research log describes an iterative extraction process. A bracket-only merger split some continuations too early; an indentation-aware merger reduced the number of entries. Case-arm support also removed a recurring failure pattern. Inspecting concrete failures was useful: it separated missing grammar forms from text segmentation problems.

But the later audit exposed the complementary risk: merging too much. The historical extractor merges more-indented lines before establishing the boundaries of individual proof steps. On this ordinary proof:

```lean
example (p q : Prop) (h : p ∧ q) : q ∧ p := by
  constructor
  · exact h.2
  · exact h.1
```

it returns one entry:

```text
constructor · exact h.2 · exact h.1
```

The entry preserves some words but loses the original structure and the intended counting unit. The grammar can accept the flattened result through a generic argument slot. Only auditing parse failures would miss it, because this problematic entry passes.

This example changes how we should interpret both coverage and keyword concentration. The counter increments `constructor` once; it does not record the two subsequent `exact` steps as separate leading keywords. A large corpus does not average this away if the segmentation rule systematically behaves that way.

Other details require care too. Lean has nested block comments; a non-greedy comment-removal regular expression is not a full nested-comment parser. Strings can contain characters that a bracket counter mistakes for syntax. Layout can distinguish nested proof structure from a wrapped argument. The historical extractor is retained for reproducibility, with those limitations documented.

<figure>
<img src="/assets/cfg/extraction.svg" width="760" height="490" alt="Three proof steps are flattened by the historical extractor into one entry beginning with constructor; the CFG can accept the flattened entry." loading="lazy">
<figcaption>The extractor defines the object that the grammar subsequently scores. Acceptance cannot repair a mistaken unit of analysis.</figcaption>
</figure>

A stronger future corpus study would use Lean-derived syntax spans or elaboration traces and retain file, location, and environment provenance. For the present article, the responsible step is to identify the historical extraction precisely and avoid presenting its entries as every independently verified tactic application in Mathlib.

## What the historical corpus table establishes

The original report records the following counts:

| Classification | Entries | Share |
|---|---:|---:|
| Named alternative | 133,224 | 92.4% |
| Generic fallback | 10,725 | 7.4% |
| Rejected | 205 | 0.14% |
| Total | 144,154 | 100% |

These figures belong to the original research log. The initial immutable corpus revision and complete extracted artifact are not included in the companion repository, so this revision does not claim to have rerun that exact corpus. A later local Mathlib checkout is identified in the provenance document and can be used for a separately labelled run.

The log also records concentrated leading-keyword usage, with a full-pass top-20 share of 84.9% and a later value of 82.4%. Those are observations from the extraction procedure. They support investigating compact action vocabularies, but they do not establish an extraction-independent distribution of all tactic applications.

[Lean4trace](https://openreview.net/forum?id=sjLWmLeJ6R) is relevant related work because it extracts training data through Lean’s elaboration machinery. Its methodology is worth studying before interpreting agreement between headline percentages as independent validation. Matching a frequency statistic does not validate a separately sampled theorem set, and repeating one extractor on another checkout does not remove its systematic errors.

The table records what motivated the experiment. Establishing a stronger claim about the distribution of tactic applications would require a corpus whose counting unit has been validated against source structure.

## Macros as a controlled interface

The original project explored a second direction: use Lean’s own macro system to create regular interfaces to useful tactics. The experiment included wrappers of this form:

```lean
macro "solve_positivity" : tactic => `(tactic| positivity)

macro "discharge_linear" e1:term:max e2:term:max : tactic =>
  `(tactic| linarith [$e1, $e2])
```

The two-argument example makes precedence a practical concern. Adjacent unrestricted term slots can interact with application parsing; the original experiment used `term:max` to bound each argument more tightly. Complex arguments may then need parentheses. The full historical macro suite and its imports are retained in the consolidated experiment file.

The contribution of a macro depends on the interface it creates. Renaming `positivity` adds little if the grammar already accepts both names with arbitrary arguments. A bounded operation with explicit slots is more interesting: the external grammar can model those slots, while the macro expands them into familiar Lean syntax.

This is a language-design option rather than evidence that macros solve arbitrary coverage. A macro definition does not guarantee that every invocation elaborates or closes a goal. Its value would need to be measured in the forms it makes expressible, the malformed arguments it excludes, and the maintenance burden it introduces.

## Designing an output language instead of only describing one

The macro idea points to a broader question from the original proposal: must the model generate exactly the surface language that human authors use? A corpus grammar tries to accommodate an existing practice. A controlled interface can instead expose a selected collection of operations with argument forms chosen for generation. These are different research objectives, even if both eventually produce Lean proof terms.

For example, an interface could distinguish a rewrite operation with a list of references from an exact operation with one supported term. It could make reverse rewriting an explicit argument rather than another piece of punctuation for the model to discover. It could expose a small compound operation that expands into several ordinary tactics. Such an interface would need a translator or macro layer, examples, and an explicit account of unsupported cases.

The attraction is maintenance at a boundary we control. Adding an operation would involve both a grammar production and its implementation. Tests could assert that accepted examples translate correctly and that malformed argument combinations fail early. Library-specific complexity could remain behind that interface where doing so does not remove useful expressive choices.

There are costs. A model already trained on Lean may be less fluent in unfamiliar wrappers. More regular syntax does not guarantee better strategy selection. A coarse operation may hide alternatives that were useful to search; a fine-grained interface may require many more generation steps. Supporting a new tactic with a macro does not demonstrate semantic completeness of a fixed finite interface.

This is therefore a hypothesis worth preserving, not a property measured by the current corpus-fit experiment. The relevant comparison would hold the task set and available operations fixed while varying their surface representation. It would measure malformed arguments, accepted coverage, output length, and ultimately task performance. Simply giving an existing keyword a new spelling would be a weak test.

That distinction also helps interpret the original ambition. A grammar can be an observational instrument, a sampling restriction, or a designed action interface. The project began with ideas about all three. The present evidence is strongest for the first two; the third remains a concrete route for future work rather than an explanation retroactively attached to the saved numbers.

## What transfers to Rocq and Isabelle

The original work also built a Rocq/SSReflect-oriented grammar and an Isar-oriented grammar. The log records 98.81% acceptance on Rocq units and 95.47% on selected Isabelle proof-step text. These are exploratory cross-system observations using distinct extraction procedures, not directly comparable measurements of language complexity.

For Rocq, proof delimiters provide helpful boundaries, but the historical splitter treats top-level periods as sentence ends and does not fully account for qualified names. For Isabelle, proof headers, quoted terms, and wrapped fact references complicate line segmentation. The Isabelle work did not include kernel execution in that environment.

The separately preserved Rocq macro file contains five small examples using `Tactic Notation`. It is useful evidence for those forms. Parenthesized term arguments working in those examples does not establish that every Rocq notation avoids precedence or argument-boundary issues.

The transferable lesson is a methodology: choose an interface, expose what it accepts, retain source provenance, and test both real examples and counterexamples. A percentage becomes informative only after its unit and acceptance language are understood.

## Reproducing the revised checks

The companion repository separates historical inputs from derived analyses. No GPU or Pantograph process is needed for the checks in this article:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements-analysis.txt
python analysis/audit.py
python -m unittest discover -s tests
```

`analysis/audit.json` records exact sample counts, acceptance decisions, the reduced-grammar disagreements, and SHA-256 hashes of the relevant inputs. The counterexamples above are checked in the test suite. A separate mutation run accepts an explicit Mathlib path and writes a new result rather than overwriting the historical table:

```bash
python post1-tactic-cfg/strength_analysis.py \
  --mathlib /path/to/mathlib4 \
  --out analysis/strength.json
```

That command intentionally uses the historical heuristic extractor. Its output is labelled accordingly; repairing arithmetic and paths does not turn extraction into a Lean parser. The provenance document explains which figures can be regenerated from saved outputs and which remain historical report entries.

A compact grammar is still a useful object to investigate. The stronger account of this work is that we can now inspect what its compactness means: a small vocabulary of named forms, a broad fallback, and a measurable tradeoff between coverage and rejection. The next question is what happens when that exact accepted language changes the model’s sampling distribution. That is the subject of the companion article.

## References

<div class="refs">
<p>Lean contributors. <a href="https://lean-lang.org/doc/reference/latest/Tactic-Proofs/Custom-Tactics/">Custom Tactics</a>. The Lean Language Reference. Syntax extensions, macros, and elaboration.</p>
<p>Nesterov, V., Kapushev, Y., and Burtsev, M. (2024). <a href="https://openreview.net/forum?id=sjLWmLeJ6R">Lean4trace: Data Augmentation for Neural Theorem Proving in Lean</a>. ICML Workshop on AI for Mathematics.</p>
<p>Lean community. <a href="https://github.com/leanprover-community/mathlib4">Mathlib</a>. The Lean 4 mathematical library. The dated mutation rerun uses revision 53c82c1c23ec418ebf7290390bc8108957bef853.</p>
</div>
