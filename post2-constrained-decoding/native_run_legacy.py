import json, time, os
from openai import OpenAI
client = OpenAI(base_url="http://127.0.0.1:8000/v1", api_key="EMPTY")
goals = [json.loads(l) for l in open("data/goals.jsonl")]
path = "results/native__goedel.jsonl"
done = set()
if os.path.exists(path):
    for l in open(path):
        r = json.loads(l)
        if "error" not in r:
            done.add((r["goal_id"], r["sample_idx"]))
out = open(path, "a")
for g in goals:
    prompt = ("Complete the following Lean 4 theorem:\n\n```lean\n"
              + g["stmt"] + " := by\n")
    for sidx in range(2):
        if (g["id"], sidx) in done:
            continue
        try:
            t0 = time.time()
            r = client.completions.create(model="m", prompt=prompt,
                                          temperature=0.8, top_p=0.95,
                                          max_tokens=500)
            out.write(json.dumps({"goal_id": g["id"], "name": g["name"],
                                  "stmt": g["stmt"], "sample_idx": sidx,
                                  "text": r.choices[0].text or "",
                                  "latency_s": round(time.time()-t0,2),
                                  "cond": "native"}, ensure_ascii=False) + "\n")
            out.flush()
        except Exception as e:
            out.write(json.dumps({"goal_id": g["id"], "error": str(e)[:200],
                                  "cond": "native"})+"\n"); out.flush()
print("DONE", len(done))
