import re, json, random, sys, os

f = "/home/stanley/mathlib4-v423/Mathlib/Algebra/Group/Basic.lean"
lines = open(f, encoding="utf-8").read().splitlines()

STMT_START = re.compile(
    r"^\s*(?:private\s+|protected\s+|noncomputable\s+)*(?:theorem|lemma)\s+[A-Za-z_][A-Za-z0-9_'!?]*")

scope_stack = [[]]
context_at = {}
for i, l in enumerate(lines):
    s = l.strip()
    if re.match(r"^section\b", s):
        scope_stack.append([])
    elif re.match(r"^end\b", s) and len(scope_stack) > 1:
        scope_stack.pop()
    elif s.startswith("variable"):
        scope_stack[-1].append(s)
    context_at[i] = [v for scope in scope_stack for v in scope]

def split_top(s, ch):
    depth = 0
    for i, c in enumerate(s):
        if c in "([{": depth += 1
        elif c in ")]}": depth -= 1
        elif c == ch and depth == 0:
            return i
    return -1

GROUP_RE = re.compile(r"([{(\[])([^{}()\[\]]*)([})\]])")
IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_'!]*")

def parse_groups(cl):
    groups = []
    for m in GROUP_RE.finditer(cl.strip()):
        kind, body, close = m.group(1), m.group(2).strip(), m.group(3)
        if not body:
            continue
        ci = split_top(body, ":")
        if ci > 0:
            names = [n for n in body[:ci].split()
                     if re.match(r"^[A-Za-z_][A-Za-z0-9_'!]*$", n)]
            typ = body[ci + 1:].strip()
            groups.append({"kind": kind, "close": close,
                           "names": names, "typ": typ,
                           "text": f"{kind}{body}{close}"})
        else:
            names = [n for n in body.split()
                     if re.match(r"^[A-Za-z_][A-Za-z0-9_'!]*$", n)]
            groups.append({"kind": kind, "close": close,
                           "names": names, "typ": "",
                           "text": f"{kind}{body}{close}"})
    return groups

def select_binders(clauses, stmt_text):
    """Mimic Lean's auto-inclusion: start from identifiers mentioned in the
    statement; add a variable group iff it mentions an included name; its
    type then contributes more names; iterate to fixpoint."""
    included = set(IDENT_RE.findall(stmt_text))
    chosen = []
    changed = True
    all_groups = []
    for cl in clauses:
        all_groups.extend(parse_groups(cl))
    while changed:
        changed = False
        for g in all_groups:
            if id(g) in {id(c) for c in chosen}:
                continue
            if any(n in included for n in g["names"]):
                chosen.append(g)
                included.update(IDENT_RE.findall(g["typ"]))
                included.update(g["names"])
                changed = True
    return chosen

stmts, seen_stmts = [], set()
i = 0
while i < len(lines):
    if STMT_START.match(lines[i]):
        j, hdr_start = i, i
        found = False
        while j < len(lines) and j - i < 15:
            hdr_start = j
            depth = 0
            for x, chx in enumerate(lines[j]):
                if chx in "([{": depth += 1
                elif chx in ")]}": depth -= 1
                elif chx == ":" and depth == 0 and lines[j][x:x+2] == ":=":
                    found = True; break
            if found: break
            j += 1
        if found:
            block = "\n".join(lines[i:hdr_start + 1])
            m = re.search(r":=", block)
            raw = re.sub(r"\s+", " ", block[:m.start()].strip())
            if 25 <= len(raw) <= 400 and "sorry" not in raw and raw not in seen_stmts:
                seen_stmts.add(raw)
                nm = re.match(
                    r"^\s*(?:(?:private|protected|noncomputable)\s+)*(?:theorem|lemma)\s+([A-Za-z_][A-Za-z0-9_'!?]*)",
                    raw)
                name = nm.group(1) if nm else "?"
                rest = raw[nm.end():].strip()
                ci = split_top(rest, ":")
                if ci > 0:
                    binders = rest[:ci].strip()
                    typ = rest[ci + 1:].strip()
                    chosen = select_binders(context_at[i], raw)
                    vars_str = " ".join(g["text"] for g in chosen)
                    binder_part = f" {binders}" if binders else ""
                    expr = f"∀ {vars_str}{binder_part}, {typ}".replace("∀ ,", "∀")
                    stmts.append({"id": len(stmts), "name": name,
                                  "file": "Mathlib/Algebra/Group/Basic.lean",
                                  "stmt": raw, "expr": expr})
        i = max(j, i) + 1
        continue
    i += 1

sys.path.insert(0, "/home/stanley/exp3")
os.environ["PATH"] = ("/home/stanley/.native-verify/pinned/lean-4.23.0-linux/bin:"
                      + os.environ.get("PATH", ""))
from kernel_loop import Repl

valid = []
repl = Repl("/home/stanley/Pantograph/.lake/build/bin/repl",
            ("Init", "Mathlib.Algebra.Group.Basic"), timeout=900,
            lean_path="/home/stanley/mathlib4-v423")
for g in stmts:
    r = repl.send("goal.start", {"expr": g["expr"]})
    if "error" in r:
        print(f"DROP {g['name']}: {str(r)[:70]}")
    else:
        valid.append(g)
repl.close()

random.Random(7).shuffle(valid)
pick = valid[:10]
with open("/home/stanley/exp3/goals_groupbasic.jsonl", "w") as out:
    for g in pick:
        out.write(json.dumps(g, ensure_ascii=False) + "\n")
print(f"\n{len(valid)}/{len(stmts)} validated; wrote {len(pick)} goals")
