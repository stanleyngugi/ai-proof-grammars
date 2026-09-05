#!/usr/bin/env python3
"""score.py -- runs ON THE POD. Scores generation output:
  1. CFG structural validity (post-hoc, original report grammar via lark/earley)
  2. leading-keyword validity (real tactic keyword from corpus frequency table)
  3. identifier hallucination rate (vs real Mathlib+Batteries name table)
  4. distinct-tactic diversity per goal
Writes results/scores__<tag>.csv and prints a summary table."""
import json, re, glob, collections, csv, sys, os, argparse
from lark import Lark, UnexpectedInput

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
DATA = os.path.join(ROOT, "..", "data")

# ---- post-hoc grammar: the ORIGINAL report grammar (identical to paper numbers)
from grammar_report import GRAMMAR, NAMED_RULES

parser = Lark(GRAMMAR, start="start", parser="earley")

def classify(line):
    try:
        tree = parser.parse(line)
        node = tree.children[0].children[0]
        rule = node.data.value if hasattr(node.data, "value") else str(node.data)
        return ("named" if rule in NAMED_RULES else "fallback", rule)
    except UnexpectedInput as e:
        return ("parse_fail", str(e).splitlines()[0][:80])

def clean_output(text):
    """Strip markdown/code fences; take first non-empty line."""
    if not text:
        return "", "empty"
    t = text.strip()
    t = re.sub(r"^```(?:lean)?\s*", "", t)
    t = re.sub(r"```\s*$", "", t)
    lines = [l.strip() for l in t.splitlines() if l.strip()]
    if not lines:
        return "", "empty"
    first = lines[0].strip()
    # flag multi-line / prose leakage
    note = ""
    if len(lines) > 1:
        note = f"multiline:{len(lines)}"
    return first, note

# ---- hallucination check (verbatim logic from lean_experiments.py §4)
CORE_ALLOWLIST = {
    "LeftInverse", "RightInverse", "Injective", "Surjective", "Bijective", "comp",
    "id", "refl", "symm", "trans", "mpr", "mp", "intro", "left", "right", "inl", "inr",
    "elim", "em", "byContradiction", "choice", "propext", "funext", "rfl", "Eq", "Iff",
    "And", "Or", "Not", "True", "False", "Nat", "Int", "List", "Option", "Prop", "Type",
    "Decidable", "DecidableEq", "Subtype", "Sigma", "Prod", "Sum", "Function",
    "cast", "ndrec", "noConfusion", "below", "brecOn",
}
AUTO_GEN_RE = re.compile(r"\.(rec|recAux|casesOn|mk|ndrec|below|brecOn|noConfusion)$")
_kw_freq = json.load(open(os.path.join(DATA, "kw_freq.json"), encoding="utf-8"))
NOT_A_LEMMA_REF = NAMED_RULES | set(_kw_freq.keys()) | {
    "rw", "simp", "simpa", "exact", "apply", "refine", "have", "obtain", "rintro",
    "intro", "intros", "ext", "rfl", "induction", "cases", "by_cases", "calc",
    "classical", "constructor", "contrapose", "suffices", "rcases", "grind",
    "gcongr", "linarith", "nlinarith", "split_ifs", "aesop", "by_contra", "change",
    "congr", "convert", "positivity", "all_goals", "dsimp", "let", "use", "ring",
    "norm_cast", "norm_num", "decide", "subst", "tauto", "omega", "assumption",
    "specialize", "push_neg", "finish", "field_simp", "simp_all", "ext1", "funext",
    "norm_cast", "abel", "polyrith", "fun_prop", "cat_disch", "finiteness",
    "unfold", "subst_vars", "use", "exact?", "apply?", "constructor?",
    # Lean 4 `induction` auto-generated hypothesis names + common fresh-binder
    # conventions inside tactic bodies (report section 6.2 bug class #3):
    "ih", "iha", "ihb", "ih1", "ih2", "hxy", "hlt", "hge",
    "fun", "if", "then", "else", "with", "at", "from", "using", "only", "by",
    "do", "in", "this", "true", "false", "abs_cases", "le_or_lt",
}

def local_binders(stmt):
    out = set()
    for m in re.finditer(r"[{(\[]\s*([^:{}()\[\]]+?)\s*:", stmt):
        for tok in m.group(1).split():
            t = tok.replace("\u207b\u00b9", "").strip()
            if t:
                out.add(t)
    return out

def extract_idents(tactic_args, stmt):
    lb = local_binders(stmt)
    # fresh binders introduced by intro-family keywords INSIDE the tactic body
    # (same bug class as report section 6.2 item 3)
    for m in re.finditer(r"\b(?:intro|intros|rintro|obtain)\s+([^;\n]+)", tactic_args):
        for tok in re.findall(r"[A-Za-z_][A-Za-z0-9_']*", m.group(1)):
            if tok not in ("fun", "with", "case"):
                lb.add(tok)
    idents = set()
    for m in re.finditer(r"[A-Za-z\u0391-\u03c9_][A-Za-z0-9_'.]*", tactic_args):
        tok = m.group(0)
        if len(tok) < 2 or tok in NOT_A_LEMMA_REF or tok in lb:
            continue
        if re.match(r"^[a-zA-Z\u0391-\u03c9]$", tok):
            continue
        idents.add(tok)
    return sorted(idents)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tag", nargs="?", default="run1")
    ap.add_argument("--out", help="Output CSV; default is analysis/scores__TAG.csv")
    args = ap.parse_args()
    tag = args.tag
    names = set(json.load(open(os.path.join(DATA, "names.json"), encoding="utf-8")))
    kw_freq = json.load(open(os.path.join(DATA, "kw_freq.json"), encoding="utf-8"))
    real_kw = set(kw_freq.keys())

    rows = []
    for path in sorted(glob.glob(os.path.join(ROOT, "results", f"*__{tag}.jsonl"))):
        cond = path.split("/")[-1].split("__")[0]
        for l in open(path):
            r = json.loads(l)
            if "error" in r:
                continue
            tactic, note = clean_output(r["text"])
            kind, rule = ("empty", "") if not tactic else classify(tactic)
            lead = re.match(r"^[A-Za-z_\u0370-\u03FF][A-Za-z0-9_'!\u0370-\u03FF]*", tactic)
            lead_tok = lead.group(0) if lead else "<punct>"
            kw_valid = lead_tok in real_kw or tactic in real_kw or lead_tok == "<punct>"
            args_part = tactic[len(lead_tok):].strip() if lead else tactic
            flagged, _ok = [], []
            idents = extract_idents(args_part, r["stmt"]) if args_part else []
            for c in idents:
                short = c.split(".")[-1]
                exists = (c in names or short in names or c in CORE_ALLOWLIST
                          or short in CORE_ALLOWLIST or bool(AUTO_GEN_RE.search(c)))
                if not exists:
                    flagged.append(c)
            sorry = bool(re.search(r"\bsorry\b|\badmit\b", tactic))
            rows.append({**r, "tactic": tactic, "kind": kind, "rule": rule,
                         "lead_tok": lead_tok, "kw_valid": kw_valid,
                         "flagged": ";".join(flagged), "sorry": sorry, "note": note})

    output = args.out or os.path.join(ROOT, "..", "analysis", f"scores__{tag}.csv")
    os.makedirs(os.path.dirname(os.path.abspath(output)), exist_ok=True)
    with open(output, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else ["x"])
        w.writeheader()
        w.writerows(rows)

    print(f"\n=== SUMMARY ({len(rows)} samples) ===")
    for cond in sorted({r["cond"] for r in rows}):
        rs = [r for r in rows if r["cond"] == cond]
        n = len(rs) or 1
        named = sum(r["kind"] == "named" for r in rs) / n
        fb = sum(r["kind"] == "fallback" for r in rs) / n
        pf = sum(r["kind"] == "parse_fail" for r in rs) / n
        empty = sum(r["kind"] == "empty" for r in rs) / n
        kwv = sum(bool(r["kw_valid"]) and r["lead_tok"] != "<punct>" for r in rs) / n
        hall = sum(1 for r in rs if r["flagged"]) / n
        sorr = sum(r["sorry"] for r in rs) / n
        lat = [r.get("latency_s", 0) for r in rs]
        # per-goal diversity of distinct tactics
        by_goal = collections.defaultdict(set)
        for r in rs:
            by_goal[r["goal_id"]].add(r["tactic"])
        div = sum(len(v) for v in by_goal.values()) / max(len(by_goal), 1)
        top_flag = collections.Counter(
            fl for r in rs for fl in (r["flagged"].split(";") if r["flagged"] else [])
        ).most_common(8)
        print(f"""
--- {cond} (n={n}) ---
  CFG named          : {named:6.1%}
  CFG fallback       : {fb:6.1%}
  CFG parse_fail     : {pf:6.1%}   (+ empty {empty:.1%})
  leading-kw real    : {kwv:6.1%}
  identifier flags   : {hall:6.1%}   top offenders: {top_flag}
  contains sorry     : {sorr:6.1%}
  distinct tactics/goal : {div:.2f}
  mean latency (n={args_n(lat)})   : {sum(lat)/max(len(lat),1):.4f}s""")

def args_n(xs):
    return len(xs)

if __name__ == "__main__":
    main()
