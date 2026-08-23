#!/usr/bin/env python3
"""kernel_loop.py -- closed-loop client for the Pantograph REPL.
Drives goal.start / goal.tactic over stdio, classifies every tactic attempt
into a FEEDBACK TAXONOMY (the measurement Post 3 is built on):

  success            -- tactic closed its branch (goals -> [])
  progress           -- valid step, subgoals remain (count delta recorded)
  no_progress        -- 'X made no progress'
  unknown_identifier -- hallucinated name (kind: lean.unknownIdentifier._namedError)
  elaboration_error  -- other semantic failure
  parse_error        -- syntactic gate failed (must be ~0 under constraint)

Usage smoke test (core-Lean, no Mathlib needed):
  python3 kernel_loop.py --smoke
"""
import argparse, json, os, subprocess, sys, time

DEFAULT_REPL = "/home/stanley/Pantograph/.lake/build/bin/repl"

class Repl:
    TOOLCHAIN_BIN = "/home/stanley/.native-verify/pinned/lean-4.23.0-linux/bin"

    def __init__(self, repl_path=DEFAULT_REPL, imports=("Init",), timeout=120,
                 lean_path=None):
        env = dict(os.environ)
        env["PATH"] = self.TOOLCHAIN_BIN + os.pathsep + env.get("PATH", "")
        if lean_path:
            # exact search path `lake env` would use for this checkout
            out = subprocess.run(
                ["lake", "env", "printenv", "LEAN_PATH"],
                cwd=lean_path, capture_output=True, text=True,
                env={**os.environ, "PATH": self.TOOLCHAIN_BIN + os.pathsep +
                     os.environ.get("PATH", "")})
            if out.returncode == 0 and out.stdout.strip():
                env["LEAN_PATH"] = out.stdout.strip()
        self.proc = subprocess.Popen(
            [repl_path, *imports], stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", bufsize=1, env=env)
        self.timeout = timeout
        # "ready." can be preceded by env-import diagnostics; scan for it
        end = time.time() + 60
        banner = ""
        while time.time() < end:
            line = self.proc.stdout.readline()
            if not line:
                err = self.proc.stderr.read() if self.proc.stderr else ""
                raise RuntimeError(f"repl died at startup. stderr: {err[-400:]}")
            if line.strip() == "ready.":
                banner = line
                break
        if not banner:
            raise RuntimeError("repl never became ready")

    def _read_json(self):
        end = time.time() + self.timeout
        while time.time() < end:
            line = self.proc.stdout.readline()
            if not line:
                raise RuntimeError("repl died")
            line = line.strip()
            if not line or line == "ready.":
                continue
            return json.loads(line)
        raise TimeoutError("repl response timed out")

    def send(self, cmd, payload):
        line = f"{cmd} {json.dumps(payload, ensure_ascii=False)}"
        self.proc.stdin.write(line + "\n")
        self.proc.stdin.flush()
        return self._read_json()

    def close(self):
        self.proc.kill()

def classify(resp, n_goals_before):
    """Map one tactic response to the feedback taxonomy."""
    if isinstance(resp, dict) and "error" in resp:
        e = str(resp.get("desc", ""))
        if "Unknown identifier" in e:
            return "unknown_identifier"
        if resp["error"] == "parse":
            return "parse_error"
        if resp["error"] == "index":
            return "protocol_error"
        return "elaboration_error"
    msgs = resp.get("messages") or []
    errs = [m for m in msgs if m.get("severity") == "error"]
    kinds = set()
    for m in errs:
        d = m.get("data", "")
        if m.get("kind") == "lean.unknownIdentifier._namedError" or \
           "Unknown identifier" in d:
            kinds.add("unknown_identifier")
        elif "made no progress" in d:
            kinds.add("no_progress")
        else:
            kinds.add("elaboration_error")
    # most-informative label wins: a hallucinated name matters more than
    # the no-progress complaint the same tactic also triggered
    for pref in ("unknown_identifier", "no_progress", "elaboration_error"):
        if pref in kinds:
            return pref
    n_after = len(resp.get("goals") or [])
    if n_after == 0:
        return "success"
    return "progress"

def run_proof(repl, goal_expr, tactics):
    """Send goal.start then tactics sequentially through state 0..n.
    Returns list of per-step records."""
    r = repl.send("goal.start", {"expr": goal_expr})
    if "error" in r:
        return [{"step": 0, "tactic": "<goal.start>",
                 "class": classify(r, 0), "raw": r}]
    sid = r.get("stateId", 0)
    records = []
    for i, tac in enumerate(tactics, 1):
        t0 = time.time()
        resp = repl.send("goal.tactic",
                         {"stateId": sid, "goalId": 0, "tactic": tac})
        dt = round(time.time() - t0, 3)
        cls = classify(resp, None)
        nxt = resp.get("nextStateId")
        rec = {"step": i, "tactic": tac, "class": cls, "latency_s": dt}
        if nxt is not None:
            sid = nxt
            rec["n_goals"] = len(resp.get("goals") or [])
        records.append(rec)
        if cls == "success":
            break
    return records

SMOKE_CASES = [
    ("∀ (p q : Prop), p ∨ q → q ∨ p",
     ["intro p q h", "cases h with | inl h => exact Or.inr h | inr h => exact Or.inl h"]),
    ("∀ (p q : Prop), p ∧ q → q ∧ p",
     ["intro p q h", "simp [and_swap]"]),          # hallucination demo
    ("∀ (p q : Prop), p ∧ q → q ∧ p",
     ["intro p q h", "exact ⟨h.right, h.left⟩"]),  # clean success
]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--repl", default=DEFAULT_REPL)
    ap.add_argument("--imports", default="Init")
    args = ap.parse_args()

    repl = Repl(args.repl, tuple(args.imports.split(",")))
    try:
        if args.smoke:
            for expr, tacs in SMOKE_CASES:
                print(f"\nGOAL {expr}")
                for rec in run_proof(repl, expr, tacs):
                    print(" ", rec)
        else:
            print("model-in-the-loop mode lands on GPU day; "
                  "harness + taxonomy validated via --smoke for now")
    finally:
        repl.close()

if __name__ == "__main__":
    main()
