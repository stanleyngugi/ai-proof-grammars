#!/usr/bin/env python3
"""strength_analysis.py -- measures the CFG's CONSTRAINT STRENGTH, the number
Post 1 explicitly does not claim: coverage of real text (99.86%) says nothing
about how much garbage the grammar rejects. This battery mutates real tactic
lines into several corruption classes and reports rejection rates per class,
plus acceptance on untouched real lines as the sanity anchor.

Classes:
  A. truncation        -- cut line at a random point (incomplete generation)
  B. english-lead      -- leading keyword replaced by an English word (prose start)
  C. wrong-tactic      -- leading keyword swapped for a different REAL tactic
                          keyword (measures discrimination, not validity)
  D1. arg-shuffle      -- arguments' tokens shuffled, keyword preserved
  D2. full-shuffle     -- all tokens shuffled
  E. prose             -- actual English sentences harvested from unconstrained
                          model generations (real model-prose, not synthetic)
  F. ident-soup        -- random identifier sequences

Also reports the hardened variant: parsed-ok lines containing reserved tokens
(sorry/admit) counted as violations -- models what a catch-all with reserved-
word exclusion would enforce.
"""
import os, re, sys, json, glob, random, importlib.util, collections

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

# import the proven extraction code from the original experiments file
spec = importlib.util.spec_from_file_location(
    "lean_experiments", os.path.join(os.path.dirname(HERE), "lean_experiments (2).py"))
LE = importlib.util.module_from_spec(spec)
spec.loader.exec_module(LE)

from grammar_report import GRAMMAR, NAMED_RULES
from lark import Lark, UnexpectedInput

parser = Lark(GRAMMAR, start="start", parser="earley")

def classify(line):
    try:
        t = parser.parse(line)
        node = t.children[0].children[0]
        rule = node.data.value if hasattr(node.data, "value") else str(node.data)
        return ("named" if rule in NAMED_RULES else "fallback", rule, None)
    except UnexpectedInput as e:
        return ("parse_fail", None, str(e).splitlines()[0][:60])

FORBIDDEN = re.compile(r"\b(?:sorry|admit)\b")

def hardened(kind, rule, line):
    """parsed-ok but contains reserved token => violation under hardened CFG"""
    if kind == "parse_fail":
        return True
    return not bool(FORBIDDEN.search(line))

# ---------- corpus ----------
MATHLIB = os.path.join(HERE, "mathlib4")
print("extracting tactic lines from local mathlib4 clone...", flush=True)
files = sorted(glob.glob(os.path.join(MATHLIB, "Mathlib", "**", "*.lean"), recursive=True))
all_lines = []
for i, f in enumerate(files):
    try:
        text = open(f, encoding="utf-8").read()
    except Exception:
        continue
    ls, _kw = LE.extract_tactic_lines(text)
    all_lines.extend(ls)
print(f"  {len(files)} files -> {len(all_lines)} logical tactic lines")

rng = random.Random(42)
N = 5000
sample = rng.sample(all_lines, min(N, len(all_lines)))
kw_freq = json.load(open(os.path.join(HERE, "data", "kw_freq.json")))
real_kws = [k for k in kw_freq.keys() if re.match(r"^[A-Za-z_][A-Za-z0-9_'!]*$", k)][:100]

ENGLISH = ["the", "we", "first", "note", "then", "this", "it", "our", "now",
           "here", "since", "because", "therefore", "however", "clearly"]

# prose harvested from real unconstrained model output
prose_pool = []
for path in glob.glob(os.path.join(HERE, "results", "*goedel*.jsonl")):
    for l in open(path, encoding="utf-8"):
        r = json.loads(l)
        txt = r.get("text") or ""
        m = re.search(r"```(?:lean)?\n.*?```", txt, re.S)
        body = txt[:m.start()] + txt[m.end():] if m else txt
        for ln in body.splitlines():
            s = ln.strip().lstrip("#*").strip()
            if len(s.split()) >= 5 and re.match(r"^[A-Za-z]", s):
                prose_pool.append(s)
prose_pool = list(dict.fromkeys(prose_pool))

def ident():
    return "".join(rng.choice("abcdefghijklmnopqrstuvwxyz_") for _ in range(rng.randint(3, 9))) + \
           str(rng.randint(0, 99)) if rng.random() < 0.3 else \
           "".join(rng.choice("abcdefghijklmnopqrstuvwxyz_") for _ in range(rng.randint(3, 9)))

def mutate(line):
    kind = rng.choice(["trunc", "eng_lead", "wrong_tac", "arg_shuf", "full_shuf", "soup"])
    toks = line.split()
    if kind == "trunc":
        cut = rng.randint(max(1, int(len(line)*0.25)), max(2, int(len(line)*0.9)))
        out = line[:cut].strip()
        cls = "A_truncation"
    elif kind == "eng_lead":
        rest = " ".join(toks[1:]) if len(toks) > 1 else ""
        out = (rng.choice(ENGLISH) + (" " + rest if rest else "")).strip() or rng.choice(ENGLISH)
        cls = "B_english_lead"
    elif kind == "wrong_tac":
        rest = " ".join(toks[1:])
        kw = rng.choice(real_kws)
        out = (kw + (" " + rest if rest else "")).strip()
        cls = "C_wrong_tactic_kw"
    elif kind == "arg_shuf":
        args = toks[1:]
        rng.shuffle(args)
        out = " ".join([toks[0]] + args)
        cls = "D1_arg_shuffle"
    elif kind == "full_shuf":
        t2 = toks[:]
        rng.shuffle(t2)
        out = " ".join(t2)
        cls = "D2_full_shuffle"
    else:
        out = " ".join(ident() for _ in range(rng.randint(2, 6)))
        cls = "F_ident_soup"
    return out.strip(), cls

results = collections.defaultdict(lambda: [0, 0])   # class -> [rejected, total]
hard_results = collections.defaultdict(lambda: [0, 0])

# sanity anchor: real lines
rej = 0; hardrej = 0
for l in sample:
    k, _r, _e = classify(l)
    rej += (k == "parse_fail")
    hardrej += not hardened(k, _r, l)
print(f"\nREAL lines (n={len(sample)}): rejected {rej} ({rej/len(sample):.2%})   "
      f"hardened-rejected {hardrej} ({hardrej/len(sample):.2%})")

mut_lines = []
for l in sample:
    out, cls = mutate(l)
    if out and out != l:
        mut_lines.append((out, cls))

for out, cls in mut_lines:
    k, _r, _e = classify(out)
    results[cls][1] += 1
    results[cls][0] += (k == "parse_fail")
    hard_results[cls][1] += 1
    hard_results[cls][0] += (not hardened(k, _r, out))

# prose class
pr = [0, 0]; prh = [0, 0]
rng.shuffle(prose_pool)
for s in prose_pool[:len(sample)]:
    k, _r, _e = classify(s)
    pr[1] += 1; pr[0] += (k == "parse_fail")
    prh[1] += 1; prh[0] += (not hardened(k, _r, s))

print(f"\n{'class':22s} {'rejected':>10s} {'hardened':>10s}    n")
order = ["A_truncation", "B_english_lead", "C_wrong_tactic_kw",
         "D1_arg_shuffle", "D2_full_shuffle", "F_ident_soup"]
for cls in order:
    rj, n = results[cls]
    hj, _ = hard_results[cls]
    print(f"{cls:22s} {rj/n:10.1%} {hj/n:10.1%}   {n}")
rj, n = pr
hj, _ = prh
print(f"{'E_model_prose':22s} {rj/n:10.1%} {hj/n:10.1%}   {n}")

tot_r = sum(v[0] for v in results.values()) ; tot_n = sum(v[1] for v in results.values())
tot_h = sum(v[0] for v in hard_results.values())
tot_h += prh[0]; tot_n += pr[1]
print(f"\nALL corruptions combined : rejected {tot_r/tot_n:.1%}   hardened {tot_h/tot_n:.1%}  (n={tot_n})")
