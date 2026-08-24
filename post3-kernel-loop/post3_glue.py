#!/usr/bin/env python3
"""post3_glue.py -- THE CLOSED LOOP. Cerebras model proposes tactics,
Pantograph kernel judges them, errors feed back as new prompts.

Per goal x sample:
  round 0: stmt -> model -> tactic -> kernel -> class
  round r: on failure, kernel error text appended to conversation, retry.

Output JSONL rows: {goal_id, name, sample_idx, round, tactic, class,
n_goals, latency_s, kernel_error}. Resumable at (goal_id, sample_idx).
"""
import argparse, json, os, sys, time, urllib.request, urllib.error, re

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kernel_loop import Repl, classify

KEY_PATH = os.path.expanduser("~/.cerebras_key")
API = "https://api.cerebras.ai/v1/chat/completions"

SYSTEM = ("You are a Lean 4 proof assistant. Given a theorem statement, you "
          "output exactly ONE Lean 4 tactic line that is a reasonable FIRST "
          "proof step. Output only the tactic, no prose, no code fences.")

def extract_tactic(text):
    if not text:
        return ""
    t = text.strip()
    t = re.sub(r"^```(?:lean)?\s*", "", t)
    t = re.sub(r"```\s*$", "", t)
    lines = [l.strip() for l in t.splitlines() if l.strip()]
    return lines[0] if lines else ""

class Cerebras:
    def __init__(self, key, model="gpt-oss-120b", max_tokens=4000):
        self.key, self.model, self.max_tokens = key, model, max_tokens
    def chat(self, messages, temperature=0.7):
        body = json.dumps({"model": self.model,
                           "max_completion_tokens": self.max_tokens,
                           "temperature": temperature, "stream": False,
                           "messages": messages}).encode()
        req = urllib.request.Request(API, data=body, headers={
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json"})
        for attempt in range(4):
            try:
                with urllib.request.urlopen(req, timeout=180) as r:
                    d = json.loads(r.read())
                return (d["choices"][0]["message"].get("content") or "",
                        d.get("usage", {}).get("total_tokens", 0))
            except urllib.error.HTTPError as e:
                if e.code == 429:
                    time.sleep(20 * (attempt + 1)); continue
                raise
        raise RuntimeError("rate limited beyond retries")

def kernel_error_text(resp):
    parts = []
    if isinstance(resp, dict):
        if "error" in resp:
            parts.append(str(resp.get("desc", "")))
        for m in resp.get("messages") or []:
            if m.get("severity") == "error":
                parts.append(m.get("data", ""))
    return " | ".join(p for p in parts if p)[:400]

def run_sample(client, repl_path, mathlib_dir, goal, sidx, rounds, out, pace):
    module = goal["file"][:-5].replace("/", ".")
    messages = [{"role": "system", "content": SYSTEM},
                {"role": "user",
                 "content": f"Theorem:\n{goal['stmt']}\n\nOutput exactly one "
                            "Lean 4 tactic line: a reasonable FIRST proof step."}]
    repl = None
    try:
        resp0 = None
        # import can be slow for heavy modules; generous timeout
        repl = Repl(repl_path, ("Init", module), timeout=900,
                    lean_path=mathlib_dir)
        expr = goal.get("expr") or goal["stmt"]
        resp0 = repl.send("goal.start", {"expr": expr})
        if "error" in resp0:
            out.write(json.dumps({"goal_id": goal["id"], "name": goal["name"],
                                  "sample_idx": sidx, "round": 0,
                                  "tactic": None, "class": "goal_start_failed",
                                  "kernel_error": str(resp0)[:200]},
                                 ensure_ascii=False) + "\n")
            out.flush(); return
        sid = resp0["stateId"]
        for rnd in range(rounds):
            text, _tok = client.chat(messages)
            tac = extract_tactic(text)
            if not tac:
                rec = {"goal_id": goal["id"], "name": goal["name"],
                       "sample_idx": sidx, "round": rnd, "tactic": "",
                       "class": "empty_output"}
            else:
                t0 = time.time()
                kresp = repl.send("goal.tactic",
                                  {"stateId": sid, "goalId": 0, "tactic": tac})
                dt = round(time.time() - t0, 3)
                cls = classify(kresp, None)
                nxt = kresp.get("nextStateId")
                n_goals = len(kresp.get("goals") or []) if nxt is not None else None
                if nxt is not None:
                    sid = nxt
                rec = {"goal_id": goal["id"], "name": goal["name"],
                       "sample_idx": sidx, "round": rnd, "tactic": tac,
                       "class": cls, "n_goals": n_goals,
                       "latency_s": dt,
                       "kernel_error": kernel_error_text(kresp)}
            out.write(json.dumps(rec, ensure_ascii=False) + "\n"); out.flush()
            print(f"  g{goal['id']} s{sidx} r{rnd}: {rec['class']:18s} {rec['tactic'][:60]}",
                  flush=True)
            if rec["class"] == "success":
                break
            messages.append({"role": "assistant",
                             "content": rec.get("tactic") or ""})
            if rec["class"] == "progress":
                errtxt = f"tactic applied but {rec['n_goals']} goals remain"
            else:
                errtxt = rec.get("kernel_error") or "invalid output"
            messages.append({"role": "user",
                             "content": "The Lean kernel rejected that step. "
                                        f"Error: {errtxt}\nProvide ONE corrected "
                                        "Lean 4 tactic line only."})
        time.sleep(pace)
    finally:
        if repl is not None:
            repl.close()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--goals", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--repl", default="/home/stanley/Pantograph/.lake/build/bin/repl")
    ap.add_argument("--mathlib-dir", default="/home/stanley/mathlib4-v423")
    ap.add_argument("--model", default="gpt-oss-120b")
    ap.add_argument("--samples", type=int, default=3)
    ap.add_argument("--rounds", type=int, default=3)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--pace", type=float, default=2.0)
    args = ap.parse_args()

    key = open(KEY_PATH).read().strip()
    client = Cerebras(key, args.model)
    goals = [json.loads(l) for l in open(args.goals, encoding="utf-8")]
    if args.limit:
        goals = goals[:args.limit]
    done = set()
    if os.path.exists(args.out):
        for l in open(args.out, encoding="utf-8"):
            r = json.loads(l)
            if r.get("round") == 0 and r.get("class") != "goal_start_failed":
                done.add((r["goal_id"], r["sample_idx"]))
        print(f"resuming: {len(done)} goal-samples already attempted")
    todo = [(g, s) for g in goals for s in range(args.samples)
            if (g["id"], s) not in done]
    print(f"{len(todo)} goal-samples queued")
    with open(args.out, "a", encoding="utf-8") as out:
        for i, (g, s) in enumerate(todo):
            try:
                run_sample(client, args.repl, args.mathlib_dir,
                           g, s, args.rounds, out, args.pace)
            except Exception as e:
                out.write(json.dumps({"goal_id": g["id"], "sample_idx": s,
                                      "round": -1, "class": "driver_error",
                                      "kernel_error": str(e)[:250]},
                                     ensure_ascii=False) + "\n")
                out.flush()
                print(f"  !! g{g['id']} driver error: {str(e)[:120]}", flush=True)
            print(f"[{i+1}/{len(todo)}]", flush=True)

if __name__ == "__main__":
    main()
