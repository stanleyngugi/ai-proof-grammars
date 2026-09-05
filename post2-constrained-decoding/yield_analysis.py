#!/usr/bin/env python3
"""Historical line selection: CFG acceptance, not kernel reachability."""
import argparse
import json
import re
from pathlib import Path
from lark import Lark, UnexpectedInput
from grammar_report import GRAMMAR

parser = Lark(GRAMMAR, parser="earley")


def lines_of(text):
    """Preserve historical selection: first closed fence or nonempty non-header lines."""
    m = re.search(r"```(?:lean)?\n(.*?)```", text, re.S)
    body = m.group(1) if m else text
    result = []
    for line in body.splitlines():
        s = line.strip().rstrip(",").strip()
        if s and not s.startswith(("--", "#", "###", "**", "Theorem:", "Proof:")):
            result.append(s)
    return result


def valid(text):
    try:
        parser.parse(text)
        return True
    except UnexpectedInput:
        return False


def measure(rows):
    total = accepted = 0
    ratios = []
    for row in rows:
        lines = lines_of(row.get("text") or "")
        n = len(lines)
        k = sum(map(valid, lines))
        total += n
        accepted += k
        if n:
            ratios.append(k/n)
    return {"selected_lines": total, "accepted_lines": accepted,
            "fraction": accepted/total if total else None,
            "mean_per_nonempty_generation": sum(ratios)/len(ratios) if ratios else None,
            "nonempty_generations": len(ratios)}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--results", type=Path, default=Path(__file__).resolve().parent / "results")
    args = ap.parse_args()
    for path in sorted(args.results.glob("*.jsonl")):
        rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
        rows = [r for r in rows if "text" in r and "error" not in r]
        print(path.name, json.dumps(measure(rows)))


if __name__ == "__main__":
    main()
