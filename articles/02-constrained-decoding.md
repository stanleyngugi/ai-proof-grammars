# How a Grammar Changes AI-Generated Mathematical Proof Steps

*The sampling mechanism, the saved results, and the boundary between grammar acceptance and Lean correctness.*

Lean is a language and tool for writing computer-checked mathematical proofs. A *tactic* is a command that advances a proof; this article studies grammars for those individual proof steps.

> **Updated September 5, 2026.** Expanded from the August 22 article with decoding mechanics, traceable examples, exact counts, and corrected metric definitions. CFG acceptance is not measured Lean validity; latency and line fractions are reported accordingly. [Original version](/archive/revisions/2026-08-22-grammar-constrained-decoding-lean-original.html) · [Evidence and reproduction](https://github.com/stanleyngugi/ai-proof-grammars/blob/main/docs/evidence.md).

A grammar changes which next tokens a language model is allowed to sample. That sounds like a formatting intervention, but its consequences propagate: once a different token is chosen, every later prediction sees a different prefix. The useful experimental question is how that change affects the outputs we actually receive.

I tested a permissive Lean tactic grammar using Qwen2.5-Coder-7B-Instruct, vLLM, and llguidance. The constrained run produced 640 outputs whose first cleaned lines were accepted by the scoring grammar, compared with 420 out of 640 in the unconstrained run. The same prompts were used in both conditions.

This article follows that result from the sampling mechanism to the exact scoring procedure. The [first article](/posts/2026-08-22-lean-tactic-language-cfg.html) explains why the grammar’s broad fallback matters. Here we examine what the intervention changed, what the saved files let us measure, and how output format can change the apparent result.

The experiment is an output-distribution study. It did not execute these generations against Lean or train a model. That boundary leaves plenty to investigate: familiar keywords, incomplete arguments, admissions, string diversity, request latency, and the difference between first-line and whole-output measurements.

## From a grammar to a next-token decision

An autoregressive model assigns probabilities to the next token given the prompt and generated prefix. A grammar-aware decoder adds a restriction: a proposed token is admissible only if appending its decoded text remains compatible with some complete output in the grammar’s language.

Let `x` be the current prefix, `v` a candidate token, and `M_G(x, v)` a zero-or-one admissibility mask. Ignoring other sampling filters for the moment, masked sampling has the form:

```text
q(v | x) = p(v | x) M_G(x, v)
           -----------------
           Σu p(u | x) M_G(x, u)
```

Invalid choices receive zero probability; the remaining choices are renormalized. The model weights do not change, but the sampled distribution does. Later tokens are conditioned on the altered prefix, so the effect can extend well beyond the first disallowed character.

For a numerical example, imagine four candidate token fragments at one prefix. The model assigns them probabilities 0.50, 0.20, 0.20, and 0.10. If the grammar excludes the last two, the surviving mass is 0.70. Their new probabilities become approximately 0.714 and 0.286.

| Hypothetical token fragment | Before masking | Allowed? | After masking |
|---|---:|---|---:|
| `mul_comm` | 0.50 | Yes | 0.714 |
| `h1` | 0.20 | Yes | 0.286 |
| closing fence | 0.20 | No | 0 |
| end-of-sequence | 0.10 | No | 0 |

These are teaching probabilities, not logits recovered from the experiment. In particular, the table supposes a prefix where a name is required and completion is not yet allowed. It shows what renormalization does without implying that the historical permissive grammar necessarily imposes those restrictions.

The relative odds between the surviving choices remain 2.5 to 1 at this step. The decoder has not supplied a theorem-relevance score; it has excluded choices. Later probabilities can nevertheless differ because the chosen continuation becomes part of the model’s context. Local masking should also not be confused with sampling exactly from the original distribution conditioned on eventual whole-string validity.

A conceptual loop looks like this:

```python
# Pseudocode: the real engine operates on tokenizer-aware masks.
while not finished:
    logits = model.next_token_logits(prompt, generated)
    allowed = matcher.allowed_token_ids()
    logits[~allowed] = float("-inf")
    token = sample(logits)
    matcher.accept(token)
    generated.append(token)
```

This code is an explanation, not the API used to run the experiment. The implementation delegates masking to vLLM’s guidance backend and llguidance. Tokenization, grammar state, termination, and engine errors are handled below the request interface. The [llguidance project](https://github.com/guidance-ai/llguidance) documents that machinery.

## A prefix is not yet a complete tactic

Consider the deliberately restricted rewrite grammar from the first article:

```lark
start: "rw" "[" name ("," name)* "]"
name: /[A-Za-z_][A-Za-z0-9_'.]*/
%import common.WS
%ignore WS
```

After the text `rw [`, an identifier can begin. After `rw [mul_`, continuing the identifier remains possible. After `rw [mul_comm`, a closing bracket can finish the output; a comma can start another list element. Ending the response before the closing bracket must not be treated as completing this grammar.

The model’s vocabulary does not consist of those grammar symbols. A token may contain part of `mul_comm`, several punctuation characters, or whitespace followed by part of a name. A correct matcher therefore reasons about a token’s entire decoded contribution. Testing only its first character or treating every token as a grammar terminal would be wrong.

A second subtlety is stopping. A valid prefix may still be incomplete when a token budget is exhausted or a request is interrupted. “Every sampled token was allowed” and “the returned string is a complete member of the grammar” are different checks. A production experiment should retain finish reasons and validate completed outputs against the actual generation grammar.

The original saved files do not record finish reasons or completion-token counts. That limits what this reanalysis can say about truncation and token efficiency. It also explains why new instrumentation cannot retroactively turn the old run into a token-level study.

<figure>
<img src="/assets/cfg/decoding.svg" width="760" height="540" alt="Model probabilities and tokenizer-aware grammar state jointly determine allowed tokens; masked sampling updates both the generated prefix and matcher state." loading="lazy">
<figcaption>The intervention happens during sampling. Post-hoc scoring is a separate operation and may even use a different grammar.</figcaption>
</figure>

## Which grammar did the experiment enforce?

The generation grammar is `post2-constrained-decoding/grammar_lean.lark`. It was adapted from the Lark scoring grammar to work with the guidance backend. It uses explicit whitespace, removes Lark rule priorities, and avoids the scoring grammar’s lookahead expression for case patterns.

These are two artifacts, not interchangeable spellings of one guaranteed-equivalent grammar. There are also differences in identifier characters, case handling, and supported structural forms. The scoring grammar’s acceptance is therefore not a sufficient test that the exact generation constraint was enforced.

Both versions share the most important design choice: permissive arguments and an identifier-led fallback. In the generation grammar:

```lark
generic_tac: ident (_WS args)?
ident: /[A-Za-z_\u0370-\u03FF][A-Za-z0-9_'!\u0370-\u03FF]*/
args: /[^\n]+/
_WS: /[ \t]+/
```

This admits much more than valid Lean tactic syntax. It can accept `sorry` through the identifier rule and accept `exact sorry` through a named tactic with arbitrary arguments. An English sentence beginning with an identifier can fit too. Comments that previously described some omitted keywords as forbidden were incorrect; the grammar language itself has been preserved while those comments were corrected.

The constraint nevertheless excludes some output forms and can alter the model’s tendency to produce them. The saved Qwen results establish an association between this configured intervention and the scored output distribution. They do not establish that every remaining output parses in Lean.

## The task and the prompt

The Qwen comparison asked for one first tactic given a theorem statement. The system message was:

```text
You are a Lean 4 proof assistant. You output only Lean 4 tactics.
```

The user prompt wrapped the extracted statement in a Lean fence, followed it with `by`, and asked for exactly one reasonable first step:

````text
Below is the statement of a real Lean 4 (Mathlib) theorem.

```lean
{stmt}
by
```

Output exactly ONE Lean 4 tactic line that would be a reasonable FIRST
proof step for this theorem. Output only the tactic itself, nothing else.
````

That formatting is part of the historical configuration. It was not a complete compilable theorem declaration, and the experiment did not validate each prompt as a standalone Lean statement. It should be reproduced faithfully when reproducing the historical setup, rather than quietly improved while claiming the same experiment.

The 80 prompts came from a seeded source-text sampler. Several depend on surrounding context absent from the prompt. The saved `card_pow_le` entry is a particularly clear extraction failure: it includes proof branches and a subsequent declaration. Random selection does not make such an entry faithful to a single theorem.

Both Qwen conditions received the same prompts, which is useful for their comparison. The prompt defects still limit generalization to well-formed theorem tasks. A statement-only task also differs from next-tactic prediction given an actual proof state with local hypotheses. No result here should be described as the latter.

## Configuration and artifacts

The historical stack recorded in the project was vLLM 0.10.2 with the guidance backend on an RTX A5000. The Qwen model was Qwen2.5-Coder-7B-Instruct. The request driver used:

| Setting | Value |
|---|---|
| Saved prompt set | 80 extracted statements |
| Samples per statement | 8 |
| Requests per sample | One, with `n=1` |
| Temperature | 0.8 |
| Top-p | 0.95 |
| Maximum output tokens | 64 |
| Task | One first tactic |
| Scoring unit | First nonempty line after cleanup |

The served model alias in the driver is `m`. The historical JSONL files do not pin a model revision or include a full server manifest. The revision therefore records the available configuration without inventing missing identifiers.

The request-level intervention was:

```python
extra_body = {
    "guided_grammar": grammar_text,
    "guided_decoding_backend": "guidance",
}
```

The unconstrained request omitted that extra body. The complete driver is retained in the repository. Its historical API shape belongs to the pinned serving stack; it is not presented as a promise that the same options work unchanged in every current vLLM version.

The raw generation files remain unchanged. Corrected analyses are written under `analysis/`, with hashes of their input files. This is important when recovering missing local artifacts: a recovered file can explain an old result, but it should not silently replace the denominator of a previously published table.

## Cleanup is part of the metric

The scorer does not parse the complete raw response. It strips an opening and closing Markdown fence when present, discards blank lines, and keeps the first remaining line. In simplified form:

```python
text = remove_outer_fences(text.strip())
lines = [line.strip() for line in text.splitlines() if line.strip()]
tactic = lines[0] if lines else ""
```

Suppose a model returns a fence containing `simp`, followed by two additional lines. The first-line score evaluates `simp`; it does not establish that the full output followed the one-line instruction. If the model returns prose before a valid tactic, the first line may instead be prose.

The original scorer also records a multiline note. Those notes should be retained alongside the score, because output-format compliance and acceptance after cleanup are different measurements. A model may violate the requested envelope while still supplying an easily recoverable tactic.

This distinction matters when comparing constrained generation with alternatives. A useful baseline is unconstrained generation with the same cleanup. Comparing cleaned constrained outputs against uncleaned unconstrained outputs would confound the decoding intervention with postprocessing. The historical Qwen scorer applies its cleanup to both arms.

The repaired scorer fixes a missing `os` import and changes the output location so regenerating scores does not overwrite the original CSVs. It preserves the historical classification and identifier heuristic for comparability.

## The Qwen result, with exact counts

Recomputing the first-line classifications from the saved outputs gives:

| Measurement | Unconstrained | Constrained |
|---|---:|---:|
| Samples | 640 | 640 |
| Named CFG alternative | 388 | 592 |
| Generic fallback | 32 | 48 |
| CFG rejected | 220 | 0 |
| Total CFG accepted | 420/640, 65.625% | 640/640, 100% |
| Leading keyword in corpus table | 385/640, 60.156% | 584/640, 91.250% |
| At least one identifier flag | 319/640, 49.844% | 339/640, 52.969% |
| Contains `sorry` or `admit` | 2/640, 0.313% | 16/640, 2.500% |
| Mean distinct strings per statement | 7.10 | 7.00 |
| Mean recorded request latency | 0.3035 s | 0.3473 s |

<figure>
<img src="/assets/cfg/qwen-acceptance.svg" width="820" height="410" alt="Of 640 Qwen samples in each condition, the unconstrained run has 388 named matches, 32 generic matches, and 220 rejections; the constrained run has 592 named matches, 48 generic matches, and no rejections." loading="lazy">
<figcaption>Classification of first cleaned lines. These are CFG outcomes, not Lean execution outcomes.</figcaption>
</figure>

The observed improvement is 34.375 percentage points. Another way to describe the same fixed-budget observation is 220 additional accepted strings across 640 requests. Neither description requires a claim about proof correctness.

The leading-keyword change is useful additional evidence that the output distribution moved toward familiar tactic names. Its reference table, however, comes from the heuristic corpus extractor discussed in the first article. It is a corpus-derived vocabulary check, not a query of the loaded Lean tactic environment.

The reduced-grammar ablation from the first article produces exactly the same acceptance decisions on these samples. This reinforces the interpretation: the result is about the broad accepted language, not evidence that every named tactic production independently supplied an essential restriction.

## Follow three saved samples through the scorer

These examples were selected to illustrate measurement categories, not to estimate their frequency. Each can be found by its `goal_id` and `sample_idx` in the named JSONL file. The analysis exports their raw text, cleaned text, and classifications in `analysis/examples.json`.

**Formatting around a plausible-looking command.** In `unconstrained__qwen.jsonl`, goal 29184, sample 1 is exactly:

```text
`apply comp_idem`
```

Those single backticks are part of the model output. The cleaner removes outer triple fences, not inline backticks, so the CFG rejects the line at its first character. Removing the two backticks would change the score. It would not tell us whether `comp_idem` resolves or whether the tactic proves anything. This is a good example of a formatting metric depending on the recovery policy.

**A recognized first line from a multiline response.** In the same file, goal 36579, sample 7 begins:

```lean
induction n with | zero => simp | succ n ih =>
```

The raw response continues with a `have`, a rewrite, a simplification, and a trailing triple fence. The first-line scorer returns a named induction match and a multiline note. The argument catch-all accepts the line even though it ends at the opening of a branch body. The score describes the selected line’s membership in the CFG, not completeness of the generated proof structure.

**An admission inside an accepted output.** Goal 110604, sample 2, again from the unconstrained file, is:

```lean
have hB_cont := continuous_comp (continuous_id ∘ f) hg.continuous; sorry
```

The grammar recognizes the leading `have` form while the separate lexical check flags `sorry`. Both labels are correct for their respective definitions. Grammar acceptance and the admission policy answer different questions about one output.

For comparison, the constrained file’s goal 29184, sample 3 is `rewrite category.id_comp`, classified as generic fallback. Constrained does not mean every output chooses a named production. The full numerical tables are needed alongside these examples because readable anecdotes alone can hide the distribution.

## Similar string diversity does not establish similar strategies

The diversity calculation groups outputs by statement and counts unique cleaned strings. Eight samples can contribute at most eight distinct strings; the observed means are 7.10 and 7.00.

This suggests that exact textual duplication did not increase dramatically in this small run. It does not establish preservation of proof-strategy diversity. `simp [h1]` and `simp [h2]` count as different strings even if they have the same effect. Two very different strings may both fail immediately. Conversely, a single tactic can invoke substantial internal proof search.

A future proving study could compare distinct successor states, successful tactic families, or completed proofs. Those measurements need an actual evaluator and a declared equivalence criterion. They are outside this saved-output analysis.

The sampling structure also matters for uncertainty. There are 80 statement groups, not 640 unrelated problems. Any interval intended to generalize across problems should account for clustering by statement. The descriptive counts above are exact for the files; they are not confidence bounds for a future model run or theorem population.

## The name checker measures flags

The identifier heuristic extracts candidate names from tactic arguments and looks them up in a source-derived name table. It excludes some keywords, local binders, familiar core names, and patterns associated with automatically generated declarations.

That makes it a useful exploratory diagnostic, but not an oracle for hallucination. A short-name lookup can approve a wrong namespace because a declaration with that final component exists elsewhere. A local variable can be flagged if the binder recognizer misses it. A legitimate core declaration may be absent from the scanned source roots. An introduced name can be mistaken for a reference.

The rate therefore should be called “generations with at least one identifier flag.” The 49.844% and 52.969% values do not justify saying half the generations definitely cite nonexistent Lean declarations.

Using the same checker on both conditions does not automatically cancel its bias. Constraints alter the forms being generated, and different forms may trigger the heuristic differently. Without a manually validated sample or environment-aware name resolution, the comparison describes changes in flags.

This is still useful information. The grammar intervention did not make the dictionary heuristic stop flagging names. That is consistent with a grammar that places almost no restrictions inside argument slots. It helps identify what this intervention leaves untouched without overstating the checker’s precision.

## Why the latency needs all its digits

Rounding both mean latencies to 0.3 seconds hides a difference. The underlying recorded means are 0.30353125 seconds and 0.347296875 seconds. The constrained run’s average request time is approximately 14.4% higher.

That difference is an observation, not an isolated measurement of grammar-engine overhead. Requests can differ in output length, scheduling, warmup, and server behaviour. The historical artifacts do not contain the token counts needed to normalize by generated length, nor an interleaved repeated-run design that isolates the intervention’s timing effect.

A careful statement is that the runs had subsecond average request latency, with a higher observed mean in the constrained condition. The experiment does not show zero cost, and the difference should not be erased by coarse rounding.

For a new throughput experiment I would log input and output token counts, time to first token, total request time, completion status, server configuration, and warmup policy. I would repeat or interleave the conditions and account for validation retries. Those are proposed measurements, not additions to the historical record.

## Goedel: several experiments, several denominators

The Goedel material is valuable because it shows how sensitive an evaluation can be to output interface and scoring unit. It is not a second clean copy of the Qwen comparison.

The model is [Goedel-Prover-V2-8B](https://arxiv.org/abs/2508.03613). The recovered artifacts include:

| Artifact | Samples | Statements | Interface and budget |
|---|---:|---:|---|
| Unconstrained first-step | 640 | 80 | Chat-style first-step setup, 64-token driver budget |
| “Constrained” first-step | 640 | 80 | Same intended setup; enforcement not established |
| Native full-proof | 139 | 69 | Text completion, intended 2 samples per statement, 500 tokens |

The native generator prefixes the statement with an unfinished Lean proof fence and asks for a completion. That differs from the chat-style instruction used for the first-step runs. The native artifact is also incomplete relative to its intended 80-statement, two-sample plan.

The historical “yield” script selects lines from the first complete fenced block if one exists. Otherwise it scans the whole output. It drops blank lines and certain headings/comments, trims whitespace and trailing commas, then applies the CFG to each retained line.

That procedure reproduces these fractions:

| Artifact | Selected lines | Accepted fraction |
|---|---:|---:|
| Qwen unconstrained | 670 | 64.9% |
| Qwen constrained | 640 | 100.0% |
| Goedel native full-proof | 1,970 | 49.9% |
| Goedel “constrained” | 640 | 84.5% |

These are fractions of selected lines, not tokens. They are not measured fractions reaching Lean, either. A line may be a fragment of a multiline term or proof construct. A valid complete proof is not generally equivalent to a collection of independently parseable lines.

An especially instructive contrast is the native Goedel file: 130 of its 139 first cleaned lines pass the CFG, while only 49.9% of its selected lines pass the line-accounting procedure. Neither number is a typo. They answer different questions about the same artifact.

The first-cleaned-line score for the recovered constrained Goedel file is 541/640, or 84.53%. Earlier score CSVs describe a smaller partial set. The revised analysis reports the recovered file explicitly rather than silently combining partial and complete denominators.

## How to establish that a constraint is active

During the original experiments, unexpected outputs raised concerns about parallel sampling and backend fallback. The research log attributed those observations to serving behaviour. The saved generations alone do not establish a general vLLM bug or its precise cause.

A stronger diagnostic uses the exact generation grammar and an output it genuinely excludes. If a deliberately tiny grammar admits only `rfl`, then a completed response containing `simp` is a clear violation. If the grammar admits arbitrary identifier-led text, an English sentence is not such a witness.

A practical enforcement check has three parts: compile the grammar through the intended backend, validate returned complete strings against that same language, and retain backend errors and termination reasons. Compare `n=1` and parallel sampling only in a minimal reproduction that isolates the setting being tested.

Post-hoc acceptance is still useful, but 100% acceptance by a broader or different grammar is not proof that masking was active. Likewise, zero Markdown fences is only a smoke test for a particular formatting symptom. It is not a general enforcement certificate.

The revised repository keeps `n=1` in the driver, documents its historical setting, and narrows the backend claims. A new run should save the configuration and enforcement evidence needed to move from suspicion to a reproducible infrastructure finding.

## Reserved words and bounded retries

The `sorry` observation is a direct lesson about alternatives. Omitting `sorry` from the named productions does not forbid it when a generic identifier rule can generate it. Excluding a top-level word also would not by itself exclude `exact sorry` inside an unrestricted term slot.

The companion wrapper applies a lexical check and retries a bounded number of times. That is a policy filter, not proof certification. A simple word-boundary check can reject harmless comments or strings and cannot establish that a completed proof has no admitted dependency.

Finite forbidden-word exclusion can be represented by suitable lexical constructions even without regex lookahead; whether a particular engine accepts a convenient expression is an implementation question. More importantly, banning a spelling and verifying a proof’s dependencies are different goals.

For an idealized independent violation probability `p`, unlimited rejection sampling needs an expected `1 / (1 - p)` attempts. At `p = 0.025`, that is about 1.026. The arithmetic explains the old “1.03” estimate, but it is not measured end-to-end overhead. A bounded wrapper can exhaust its attempts, and real retry distributions need not satisfy the simplifying assumption.

## Optional reasoning is a separate experiment

The original architecture proposed allowing informal reasoning before activating the formal grammar. The saved Qwen experiment instead asks for a tactic directly. Those arrangements should be distinguished:

```text
A: prompt → constrained tactic
B: prompt → free reasoning → constrained formal block
```

[CRANE](https://arxiv.org/abs/2502.09061) studies reasoning-augmented constraints and motivates this distinction. It does not establish which arrangement works better for these Lean prompts. Nor does the fact that a formal language is infinite prove that every restriction preserves every useful reasoning path.

A controlled comparison would hold total generation cost fixed, account for the reasoning tokens, and implement switching correctly across tokenizer boundaries. Informal tokens may contribute to the eventual answer; their absence from a tactic grammar is not evidence that they were wasted.

This matters for the interpretation of the native full-proof outputs. A model’s preferred generation interface, including any reasoning or scaffolding, should be understood before its lines are classified as losses. The right experiment can still find that direct constrained tactics are more efficient. That result needs to be measured rather than assumed.

## What the experiment does and does not establish

The main supported result is a substantial increase in first-cleaned-line CFG acceptance for the saved Qwen run, together with more corpus-recognized leading keywords and similar exact-string diversity. Identifier flags remain common. Recorded average latency is higher in the constrained condition. The grammar itself remains permissive.

The experiment does not measure Lean parser acceptance, tactic execution, proof completion, token savings, or training improvement. Lean’s parser and elaborator produce feedback before final proof checking; a parse failure can itself be an observable diagnostic. Describing every parse failure as “silence” obscures that distinction.

Training efficiency is a further question. Failed outputs can receive below-average group rewards and contribute an optimization signal, so multiplying group size by syntax acceptance is not generally a count of gradient-contributing rollouts. The underlying algorithm is described in [DeepSeekMath](https://arxiv.org/html/2402.03300v3).

Related work should be scoped similarly. Grammar-based tactic construction predates this project, including [ASTactic](https://proceedings.mlr.press/v97/yang19a/yang19a.pdf). That approach is distinct from masking the token vocabulary of a pretrained LLM. A public [LeanGCD project](https://ai.math.uw.edu/projects/spring-2026/) also targets Lean-specific constrained generation. This article offers an inspectable experiment, not a claim to have established an uncontested first.

## Reproduce the analysis before extending the system

The revised companion repository keeps the saved JSONL inputs and original CSVs, writes derived outputs separately, and makes the CPU analysis independent of GPU serving:

```bash
pip install -r requirements-analysis.txt
python analysis/audit.py
python post2-constrained-decoding/score.py qwen
python post2-constrained-decoding/yield_analysis.py
python -m unittest discover -s tests
```

`analysis/audit.json` includes raw-file hashes, sample and goal counts, classification totals, line accounting, timing summaries, and the reduced-grammar comparison. The article figures are generated from those results. The provenance document identifies recovered files and historical measurements that cannot be reconstructed exactly.

Proof-state interaction and training are preserved as a separate project, with their open questions documented. The CFG experiment can be understood and improved independently. Its next useful extensions are tighter supported grammars, stronger enforcement diagnostics, faithful inputs, and controlled output-interface comparisons. Each asks a specific question about generation before making claims about the larger proving system.

## References

<div class="refs">
<p>Hui, B., et al. (2024). <a href="https://arxiv.org/abs/2409.12186">Qwen2.5-Coder Technical Report</a>. arXiv:2409.12186.</p>
<p>Lin, Y., et al. (2025). <a href="https://arxiv.org/abs/2508.03613">Goedel-Prover-V2: Scaling Formal Theorem Proving with Scaffolded Data Synthesis and Self-Correction</a>. arXiv:2508.03613.</p>
<p>Guidance contributors. <a href="https://github.com/guidance-ai/llguidance">llguidance</a>. Tokenizer-aware grammar constraints and structured generation.</p>
<p>Kwon, W., et al. (2023). <a href="https://arxiv.org/abs/2309.06180">Efficient Memory Management for Large Language Model Serving with PagedAttention</a>. SOSP 2023. The vLLM serving system.</p>
<p>Banerjee, D., Suresh, T., Ugare, S., Misailovic, S., and Singh, G. (2025). <a href="https://arxiv.org/abs/2502.09061">CRANE: Reasoning with constrained LLM generation</a>. arXiv:2502.09061.</p>
<p>Shao, Z., et al. (2024). <a href="https://arxiv.org/abs/2402.03300">DeepSeekMath: Pushing the Limits of Mathematical Reasoning in Open Language Models</a>. arXiv:2402.03300. Introduces GRPO.</p>
<p>Yang, K., and Deng, J. (2019). <a href="https://proceedings.mlr.press/v97/yang19a.html">Learning to Prove Theorems via Interacting with Proof Assistants</a>. ICML, PMLR 97, pp. 6984–6994. Introduces ASTactic and CoqGym.</p>
<p>University of Washington AI for Math. <a href="https://ai.math.uw.edu/projects/spring-2026/">LeanGCD</a>. Spring 2026 project listing; cited as related ongoing work.</p>
</div>
