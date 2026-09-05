#!/usr/bin/env python3
"""Optional lexical retry policy, not a Lean proof-safety guarantee.

A word-boundary check deliberately over-rejects comments/strings and may reject
names containing a dotted component 'sorry'. It does not detect all ways a Lean
proof can depend on admissions. Use actual proof checks for that purpose.
"""
import re

FORBIDDEN = re.compile(r"\b(?:sorry|admit)\b")


def hardened_chat(client, *, grammar, n_trials=4, **kw):
    """Return (nonempty text, attempts); raise if every output violates policy."""
    if n_trials < 1:
        raise ValueError("n_trials must be positive")
    extra = dict(kw.pop("extra_body", {}) or {})
    extra.update(guided_grammar=grammar, guided_decoding_backend="guidance")
    kw["n"] = 1
    for i in range(n_trials):
        r = client.chat.completions.create(**kw, extra_body=extra)
        text = r.choices[0].message.content or ""
        if text.strip() and not FORBIDDEN.search(text):
            return text, i + 1
    raise RuntimeError(f"No output satisfied lexical policy in {n_trials} attempts")
