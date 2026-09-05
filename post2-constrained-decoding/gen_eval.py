#!/usr/bin/env python3
"""gen_eval.py -- runs ON THE POD. Head-to-head generation:
  cond=unconstrained : raw sampling
  cond=constrained   : grammar-masked decoding via vLLM structured outputs
Writes results/<cond>__<tag>.jsonl with one row per generated sample."""
import argparse, json, os, time

PROMPT_SYS = "You are a Lean 4 proof assistant. You output only Lean 4 tactics."
PROMPT_USER = (
    "Below is the statement of a real Lean 4 (Mathlib) theorem.\n\n"
    "```lean\n{stmt}\nby\n```\n\n"
    "Output exactly ONE Lean 4 tactic line that would be a reasonable FIRST "
    "proof step for this theorem. Output only the tactic itself, nothing else."
)

def gen(client, model, stmt, temp, max_tokens, grammar=None):
    """One sample per request (n=1): The historical experiment used n=1.
    Backend enforcement must be checked against the exact generation grammar."""
    kw = dict(model=model, n=1, temperature=temp, top_p=0.95,
              max_tokens=max_tokens,
              messages=[{"role": "system", "content": PROMPT_SYS},
                        {"role": "user", "content": PROMPT_USER.format(stmt=stmt)}])
    if grammar is not None:
        t0 = time.time()
        r = client.chat.completions.create(
            **kw, extra_body={"guided_grammar": grammar,
                              "guided_decoding_backend": "guidance"})
        return r.choices[0].message.content or "", time.time() - t0
    t0 = time.time()
    r = client.chat.completions.create(**kw)
    return r.choices[0].message.content or "", time.time() - t0

def completed_samples(path):
    """An API error is retryable; one successful sample does not finish a goal."""
    with open(path, encoding="utf-8") as f:
        return {(r["goal_id"], r["sample_idx"]) for line in f
                for r in [json.loads(line)]
                if "error" not in r and "text" in r and "sample_idx" in r}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cond", choices=["unconstrained", "constrained"], required=True)
    ap.add_argument("--base-url", default="http://127.0.0.1:8000/v1")
    ap.add_argument("--model", default="m")
    ap.add_argument("--tag", default="run1")
    ap.add_argument("--n", type=int, default=8)
    ap.add_argument("--temp", type=float, default=0.8)
    ap.add_argument("--max-tokens", type=int, default=64)
    ap.add_argument("--goals", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "goals.jsonl"))
    ap.add_argument("--grammar", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "grammar_lean.lark"))
    ap.add_argument("--limit", type=int, default=0, help="only first N goals (debug)")
    args = ap.parse_args()

    goals = [json.loads(l) for l in open(args.goals)]
    if args.limit:
        goals = goals[:args.limit]
    from openai import OpenAI
    client = OpenAI(base_url=args.base_url, api_key="EMPTY")
    grammar = open(args.grammar).read() if args.cond == "constrained" else None

    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results", f"{args.cond}__{args.tag}.jsonl")
    os.makedirs(os.path.join(os.path.dirname(os.path.abspath(__file__)), "results"), exist_ok=True)
    done_ids = set()
    if os.path.exists(out_path):
        done_ids = completed_samples(out_path)
        print(f"resuming: {len(done_ids)} samples already done")

    with open(out_path, "a") as f:
        for i, g in enumerate(goals):
            for sidx in range(args.n):
                if (g["id"], sidx) in done_ids:
                    continue
                try:
                    text, dt = gen(client, args.model, g["stmt"],
                                   args.temp, args.max_tokens, grammar)
                    f.write(json.dumps({
                        "goal_id": g["id"], "name": g["name"],
                        "stmt": g["stmt"], "sample_idx": sidx,
                        "text": text,
                        "latency_s": round(dt, 2), "cond": args.cond,
                    }, ensure_ascii=False) + "\n")
                    f.flush()
                except Exception as e:
                    f.write(json.dumps({"goal_id": g["id"], "sample_idx": sidx, "error": str(e)[:300],
                                        "cond": args.cond}) + "\n")
                    f.flush()
                    print(f"  !! goal {g['id']} error: {str(e)[:150]}")
            if (i + 1) % 10 == 0:
                print(f"  [{i+1}/{len(goals)}]", flush=True)
    print("DONE", out_path)

if __name__ == "__main__":
    main()
