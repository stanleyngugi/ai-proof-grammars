#!/usr/bin/env python3
"""prep_data.py -- builds from a fresh mathlib4(+batteries) source checkout:
  - names.json    : every real declaration short-name (hallucination oracle)
  - goals.jsonl   : N sampled real theorem statements (unbiased, seeded)
  - kw_freq.json  : leading-keyword frequency table (real-tactic-keyword oracle)

Usage:
  python3 prep_data.py [--mathlib PATH] [--batteries PATH] [--out DIR] [-n 80]

Defaults assume clones placed next to this file's parent directory:
  ../mathlib4   ../batteries
"""
import re, os, sys, json, glob, random, collections, argparse

HERE = os.path.dirname(os.path.abspath(__file__))

ap = argparse.ArgumentParser()
ap.add_argument("--mathlib", default=os.path.join(HERE, "..", "mathlib4"))
ap.add_argument("--batteries", default=os.path.join(HERE, "..", "batteries"))
ap.add_argument("--out", default=os.path.join(HERE, "..", "data"))
ap.add_argument("-n", dest="n_goals", type=int, default=80)
args = ap.parse_args()

MATHLIB, BATTERIES, OUT = args.mathlib, args.batteries, args.out
N_GOALS = args.n_goals
os.makedirs(OUT, exist_ok=True)

# ---------------- name extraction
DECL_RE = re.compile(
    r"^\s*(?:@\[[^\]]*\]\s*)?(?:private\s+|protected\s+|noncomputable\s+)*"
    r"(?:theorem|lemma|def|abbrev|instance)\s+"
    r"([A-Za-z_][A-Za-z0-9_'.]*)",
    re.M,
)

def extract_names():
    names = set()
    for root in (MATHLIB, BATTERIES):
        for f in glob.glob(os.path.join(root, "**/*.lean"), recursive=True):
            try:
                text = open(f, encoding="utf-8", errors="ignore").read()
            except Exception:
                continue
            text = re.sub(r"/-.*?-/", "", text, flags=re.S)
            text = re.sub(r"--.*", "", text)
            for m in DECL_RE.finditer(text):
                names.add(m.group(1))
    return sorted(set(n.split(".")[-1] for n in names if len(n) >= 2))

# ---------------- tactic-line extraction (colGt-aware continuation merging;
# a bracket-only merger under-merges real multi-line tactics -- see README)
COMMAND_KWS = {
    'theorem', 'lemma', 'def', 'instance', 'structure', 'class', 'namespace', 'end',
    'open', 'import', 'variable', 'variables', 'section', 'noncomputable', 'private',
    'protected', 'abbrev', 'example', 'alias', 'attribute', 'module', 'public',
    'macro', 'macro_rules', 'syntax', 'elab', 'notation', 'deriving', 'mutual',
    'universe', 'set_option', 'initialize', 'builtin_initialize',
}
BRACKET_OPEN = {'(': ')', '[': ']', '{': '}', '\u27e8': '\u27e9'}
BRACKET_CLOSE = {v: k for k, v in BRACKET_OPEN.items()}
TACTIC_START_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_'!]*)")

def strip_comments(text):
    text = re.sub(r'/-.*?-/', '', text, flags=re.S)
    text = re.sub(r'--.*', '', text)
    return text

def indent_of(line):
    return len(line) - len(line.lstrip(' '))

def bracket_delta(line):
    depth = 0
    for ch in line:
        if ch in BRACKET_OPEN:
            depth += 1
        elif ch in BRACKET_CLOSE:
            depth -= 1
    return depth

def merge_continuations(raw_lines):
    merged, buf, buf_indent, depth = [], None, None, 0
    i, n = 0, len(raw_lines)
    while i < n:
        line = raw_lines[i]
        if buf is None:
            if not line.strip():
                i += 1
                continue
            buf, buf_indent, depth = line, indent_of(line), bracket_delta(line)
            i += 1
            continue
        cur_indent = indent_of(line) if line.strip() else None
        looks_like_new_tactic = False
        if line.strip():
            m = TACTIC_START_RE.match(line.strip())
            fw = m.group(1) if m else None
            starts_bullet = line.strip()[0] in '\u00b7|'
            looks_like_new_tactic = (
                cur_indent is not None and cur_indent <= buf_indent
                and (fw is not None or starts_bullet)
            )
        if depth > 0 or (line.strip() and cur_indent is not None
                         and cur_indent > buf_indent and not looks_like_new_tactic):
            buf += ' ' + line.strip()
            depth += bracket_delta(line)
            i += 1
            continue
        merged.append((buf_indent, buf))
        buf, depth = None, 0
    if buf is not None:
        merged.append((buf_indent, buf))
    return merged

def extract_tactic_lines(text):
    text = strip_comments(text)
    merged = merge_continuations(text.splitlines())
    stack, out = [], []
    kw_counter = collections.Counter()
    for ind, line in merged:
        while stack and ind <= stack[-1]:
            stack.pop()
        in_block = bool(stack)
        stripped = line.strip()
        if in_block:
            m = TACTIC_START_RE.match(stripped)
            fw = m.group(1) if m else None
            if fw not in COMMAND_KWS:
                out.append(stripped)
                kw_counter[fw or '<punct-start>'] += 1
        for m in re.finditer(r'(?<![A-Za-z0-9_])by(?![A-Za-z0-9_])', line):
            stack.append(ind)
            after = line[m.end():].strip()
            if after:
                fw_m = TACTIC_START_RE.match(after)
                fw = fw_m.group(1) if fw_m else None
                if fw not in COMMAND_KWS:
                    out.append(after)
                    kw_counter[fw or '<punct-start>'] += 1
            break
    return out, kw_counter

def build_kw_freq():
    total = collections.Counter()
    n_files = 0
    for f in glob.glob(os.path.join(MATHLIB, "**/*.lean"), recursive=True):
        try:
            text = open(f, encoding="utf-8").read()
        except Exception:
            continue
        _, kw = extract_tactic_lines(text)
        total.update(kw)
        n_files += 1
    return total, n_files

# ---------------- statement sampling
STMT_START = re.compile(r"^\s*(?:private\s+|protected\s+|noncomputable\s+)*(?:theorem|lemma)\s+[A-Za-z_][A-Za-z0-9_'!?]*")
ATTR_LINE = re.compile(r"^\s*(@\[[^\]]*\]|attribute\b)")

def sample_statements(k=N_GOALS, seed=42):
    rng = random.Random(seed)
    stmts, seen = {}, set()
    files = sorted(glob.glob(os.path.join(MATHLIB, "Mathlib", "**/*.lean"), recursive=True))
    for f in files:
        try:
            lines = open(f, encoding="utf-8").read().splitlines()
        except Exception:
            continue
        i = 0
        while i < len(lines):
            l = lines[i]
            if STMT_START.match(l):
                j, hdr = i, []
                found = False
                while j < len(lines) and j - i < 15:
                    hdr.append(lines[j].rstrip())
                    if re.search(r":=\s*$|:=\s*\S", lines[j]):
                        found = True
                        break
                    j += 1
                if found:
                    block = "\n".join(hdr)
                    m = re.search(r":=", block)
                    stmt = block[:m.start()].strip()
                    stmt_one = re.sub(r"\s+", " ", stmt)
                    if (25 <= len(stmt_one) <= 350 and "sorry" not in stmt_one
                            and stmt_one not in seen):
                        seen.add(stmt_one)
                        nm = re.match(r"^\s*(?:\w+\s+)*(theorem|lemma)\s+([A-Za-z0-9_'!?]+)", stmt)
                        stmts[len(stmts)] = {
                            "id": len(stmts), "name": nm.group(2) if nm else "?",
                            "file": os.path.relpath(f, MATHLIB),
                            "stmt": stmt_one,
                        }
                i = max(j, i) + 1
                continue
            i += 1
    idx = rng.sample(list(stmts.keys()), min(k, len(stmts)))
    return [stmts[i] for i in idx]

if __name__ == "__main__":
    print("extracting declaration names...", flush=True)
    names = extract_names()
    json.dump(names, open(os.path.join(OUT, "names.json"), "w"))
    print(f"  {len(names)} unique short names")
    print("scanning tactic keywords (full corpus)...", flush=True)
    freq, nf = build_kw_freq()
    json.dump(dict(freq.most_common(400)), open(os.path.join(OUT, "kw_freq.json"), "w"))
    top20 = sum(v for _, v in freq.most_common(20)) / sum(freq.values())
    print(f"  {nf} files, {sum(freq.values())} tactic lines, top-20 share {top20:.1%}")
    print("sampling statements...", flush=True)
    goals = sample_statements()
    with open(os.path.join(OUT, "goals.jsonl"), "w") as f:
        for g in goals:
            f.write(json.dumps(g, ensure_ascii=False) + "\n")
    print(f"  {len(goals)} statements sampled")
    print("DONE")
