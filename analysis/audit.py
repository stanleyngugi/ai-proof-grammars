#!/usr/bin/env python3
"""Recompute article evidence from immutable saved outputs; CPU only, no Lean/API."""
from pathlib import Path
import collections
import hashlib
import importlib.util
import json
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
EXP = ROOT / "post2-constrained-decoding"
sys.path.insert(0, str(EXP))
import score
from lark import Lark, UnexpectedInput

REDUCED = r'''start: tactic
?tactic: generic_tac | focus_tac | case_arm_tac
generic_tac: IDENT ARGS?
focus_tac: "·" tactic
case_arm_tac: "|" CASE_PATTERN "=>" tactic?
CASE_PATTERN: /[^=]+?(?=\s*=>)/
IDENT: /[A-Za-z_][A-Za-z0-9_'!]*/
ARGS: /.+/
%import common.WS
%ignore WS
'''


def accepts(parser, text):
    try:
        parser.parse(text)
        return True
    except UnexpectedInput:
        return False


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    reduced = Lark(REDUCED, parser="earley")
    names = set(json.loads((ROOT / "data/names.json").read_text()))
    real_kw = set(json.loads((ROOT / "data/kw_freq.json").read_text()))
    spec = importlib.util.spec_from_file_location("yield_module", EXP / "yield_analysis.py")
    ym = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ym)
    summaries = {}
    manifests = {}
    selected = []
    example_keys = {
        ("unconstrained__qwen", 29184, 1),
        ("unconstrained__qwen", 36579, 7),
        ("unconstrained__qwen", 110604, 2),
        ("constrained__qwen", 29184, 3),
    }
    for path in sorted((EXP / "results").glob("*.jsonl")):
        records = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
        rows = [r for r in records if "text" in r and "error" not in r]
        counts = collections.Counter()
        by_goal = collections.defaultdict(set)
        mismatches = []
        for r in rows:
            tac, _ = score.clean_output(r["text"])
            kind, _ = score.classify(tac) if tac else ("empty", "")
            if (path.stem, r["goal_id"], r["sample_idx"]) in example_keys:
                selected.append({"file": str(path.relative_to(ROOT)), **r,
                                 "cleaned": tac, "kind": kind,
                                 "note": score.clean_output(r["text"])[1]})
            counts[kind] += 1
            old_ok = kind in ("named", "fallback")
            if accepts(reduced, tac) != old_ok:
                mismatches.append({"goal_id": r["goal_id"], "sample_idx": r["sample_idx"], "text": tac})
            lead = score.re.match(r"^[A-Za-z_\u0370-\u03FF][A-Za-z0-9_'!\u0370-\u03FF]*", tac)
            token = lead.group(0) if lead else "<punct>"
            counts["known_leading_keyword"] += token != "<punct>" and (token in real_kw or tac in real_kw)
            args = tac[len(token):].strip() if lead else tac
            idents = score.extract_idents(args, r["stmt"]) if args else []
            flagged = [c for c in idents if not (
                c in names or c.split(".")[-1] in names or c in score.CORE_ALLOWLIST
                or c.split(".")[-1] in score.CORE_ALLOWLIST or score.AUTO_GEN_RE.search(c))]
            counts["identifier_flagged"] += bool(flagged)
            counts["sorry_or_admit"] += bool(score.re.search(r"\bsorry\b|\badmit\b", tac))
            by_goal[r["goal_id"]].add(tac)
        lat = [r["latency_s"] for r in rows if "latency_s" in r]
        pairs = collections.Counter((r["goal_id"], r["sample_idx"]) for r in rows)
        summaries[path.stem] = {
            "records": len(records), "samples": len(rows), "errors": len(records)-len(rows),
            "goals": len(by_goal), "duplicate_sample_keys": sum(n-1 for n in pairs.values()),
            "classification_counts": dict(counts),
            "mean_latency_s": statistics.mean(lat) if lat else None,
            "median_latency_s": statistics.median(lat) if lat else None,
            "mean_distinct_strings_per_goal": statistics.mean(map(len, by_goal.values())) if by_goal else None,
            "reduced_grammar_disagreements": mismatches,
            "line_accounting": ym.measure(rows),
        }
        manifests[str(path.relative_to(ROOT))] = digest(path)
    for path in [ROOT / "data/goals.jsonl", ROOT / "data/names.json", ROOT / "data/kw_freq.json",
                 EXP / "grammar_report.py", EXP / "grammar_lean.lark", EXP / "score.py",
                 EXP / "yield_analysis.py", Path(__file__).resolve()]:
        manifests[str(path.relative_to(ROOT))] = digest(path)
    examples = ["The first step is to induct on the structure of n.", "rw [", "exact (",
                "sorry", "rfl nonsense", "simp [DefinitelyNotReal]"]
    output = {"scope": "Saved-output CFG and heuristic analysis; no Lean verification or GPU rerun",
              "runs": summaries, "counterexamples": {t: score.classify(t)[0] for t in examples},
              "sha256": manifests}
    (ROOT / "analysis/audit.json").write_text(json.dumps(output, indent=2, ensure_ascii=False)+"\n")
    (ROOT / "analysis/examples.json").write_text(json.dumps({
        "selection": "Illustrative categories, not a representative random sample",
        "examples": selected}, indent=2, ensure_ascii=False)+"\n")
    for name, s in summaries.items():
        c = s["classification_counts"]
        print(f"{name}: {s['samples']} samples, {s['goals']} goals, "
              f"{c.get('named', 0)+c.get('fallback', 0)} CFG accepted; "
              f"mean latency {s['mean_latency_s']:.4f}s", flush=True)


if __name__ == "__main__":
    main()
