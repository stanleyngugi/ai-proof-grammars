#!/usr/bin/env python3
"""yield_analysis.py -- reframes results through the feedback-yield lens:
what fraction of generated tactic LINES can reach the kernel (syntactically
evaluable), per condition. Kernel-reachable line = parses under the CFG."""
import json, re, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lark import Lark, UnexpectedInput
from grammar_report import GRAMMAR, NAMED_RULES

lp = Lark(GRAMMAR, start="start", parser="earley")

def kind(line):
    try:
        t = lp.parse(line)
        node = t.children[0].children[0]
        rule = node.data.value if hasattr(node.data, "value") else str(node.data)
        return "named" if rule in NAMED_RULES else "fallback"
    except (UnexpectedInput, Exception):
        return "parse_fail"

def lines_of(text):
    """Tactic-candidate lines from a generation: fenced block if present,
    else nonempty non-header lines; strips bullets/commas."""
    m = re.search(r"```(?:lean)?\n(.*?)```", text, re.S)
    body = m.group(1) if m else text
    out = []
    for ln in body.splitlines():
        s = ln.strip().rstrip(",").strip()
        if not s or s.startswith(("--", "#", "###", "**", "Theorem:", "Proof:")):
            continue
        out.append(s)
    return out

def report(path, label):
    rows = [json.loads(l) for l in open(path, encoding="utf-8") if '"text"' in l]
    tot = ok = 0
    per_gen_yield = []
    for r in rows:
        ls = lines_of(r.get("text") or "")
        ks = [kind(x) for x in ls]
        n = len(ks)
        k = sum(1 for x in ks if x != "parse_fail")
        tot += n; ok += k
        if n:
            per_gen_yield.append(k / n)
    avg = sum(per_gen_yield) / max(len(per_gen_yield), 1)
    print(f"{label:34s} lines={tot:5d}  kernel-reachable={ok/tot:6.1%}   "
          f"mean per-gen yield={avg:6.1%}")

base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
report(os.path.join(base, "unconstrained__qwen.jsonl"), "Qwen unconstrained (1st-tac)")
report(os.path.join(base, "constrained__qwen.jsonl"), "Qwen constrained (1st-tac)")
report(os.path.join(base, "native__goedel.jsonl"), "Goedel native (full proofs)")
report(os.path.join(base, "constrained__goedel.jsonl"), "Goedel 'constrained' (degraded*)")
