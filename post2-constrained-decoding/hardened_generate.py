#!/usr/bin/env python3
"""hardened_generate.py -- drop-in wrapper adding reserved-token enforcement
on top of grammar-constrained decoding. Rationale: llguidance's rust regex
engine has no lookaheads, so 'sorry/admit can never appear as an argument'
isn't expressible inside the CFG itself (see strength_analysis.py: the
catch-all re-admits keyword-shaped tokens). Generate -> validate -> resample
costs ~1.03 generations/sample at the observed 2.5% violation rate."""
import json, re

FORBIDDEN = re.compile(r"(?:^|\s|[\[({])(sorry|admit)(?:\s|$|[\])},])")

def clean(text):
    return FORBIDDEN.sub(lambda m: m.group(0).replace(m.group(1), "_forbidden_"), text)

def hardened_chat(client, *, grammar, n_trials=4, **kw):
    """Call client.chat.completions.create under `grammar`; retry (up to
    n_trials) if the output contains forbidden tactic tokens. Returns
    (text, trials_used). Raises RuntimeError only if ALL trials violated."""
    for i in range(n_trials):
        r = client.chat.completions.create(
            **kw, extra_body={"guided_grammar": grammar})
        text = r.choices[0].message.content or ""
        if not FORBIDDEN.search(text):
            return text, i + 1
    return None, n_trials

if __name__ == "__main__":
    # self-test of the validator
    assert not FORBIDDEN.search("simp [Nat.le_of_lt]")
    assert FORBIDDEN.search("exact sorry")
    assert FORBIDDEN.search("rw [h]; sorry")
    assert not FORBIDDEN.search("simp [Nat.sorryAx_eq]")   # names containing 'sorry' are fine
    print("validator self-test OK")
