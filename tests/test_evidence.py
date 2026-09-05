"""Regression checks for measurement boundaries, data integrity, and retry policy."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "post2-constrained-decoding"))
import score
import gen_eval
import hardened_generate
import yield_analysis
from lark import Lark, UnexpectedInput


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


audit = load("audit", ROOT / "analysis/audit.py")
legacy = load("legacy", ROOT / "post1-tactic-cfg/lean_experiments.py")
strength = load("strength", ROOT / "post1-tactic-cfg/strength_analysis.py")


class Measurements(unittest.TestCase):
    def test_actual_scoring_counterexamples(self):
        for text in ["rw [", "exact (", "sorry", "rfl nonsense", "The first step is to induct."]:
            with self.subTest(text=text):
                self.assertIn(score.classify(text)[0], ("named", "fallback"))

    def test_strict_teaching_grammar_checks_brackets(self):
        grammar = r'''start: "rw" "[" name ("," name)* "]"
name: /[A-Za-z_][A-Za-z0-9_'.]*/
%import common.WS
%ignore WS'''
        parser = Lark(grammar, parser="earley")
        parser.parse("rw [mul_comm]")
        for text in ["rw [", "rw [mul_comm", "rw [← mul_comm]"]:
            with self.assertRaises(UnexpectedInput):
                parser.parse(text)

    def test_cleanup_is_not_raw_format_compliance(self):
        self.assertEqual(score.clean_output("```lean\nsimp\nexact h\n```"), ("simp", "multiline:2"))
        self.assertEqual(score.classify(score.clean_output("`apply comp_idem`")[0])[0], "parse_fail")

    def test_extraction_limitation_remains_visible(self):
        source = "example (p q : Prop) (h : p ∧ q) : q ∧ p := by\n  constructor\n  · exact h.2\n  · exact h.1\n"
        entries, _ = legacy.extract_tactic_lines(source)
        self.assertEqual(entries, ["constructor · exact h.2 · exact h.1"])

    def test_line_denominators_and_empty_output(self):
        result = yield_analysis.measure([{"text": "simp\n`bad`"}, {"text": "simp"}, {"text": ""}])
        self.assertEqual((result["accepted_lines"], result["selected_lines"]), (2, 3))
        self.assertEqual(result["mean_per_nonempty_generation"], .75)
        self.assertIsNone(yield_analysis.measure([])["fraction"])

    def test_aggregate_includes_prose_rejections(self):
        self.assertEqual(strength.aggregate({"shuffle": [3, 10]}, [4, 5]), (7, 15))
        self.assertFalse(strength.hardened("parse_fail", None, "```"))
        self.assertFalse(strength.hardened("named", None, "exact sorry"))

    def test_saved_qwen_ablation_and_sample_keys(self):
        reduced = Lark(audit.REDUCED, parser="earley")
        for condition, expected in [("unconstrained", 420), ("constrained", 640)]:
            path = ROOT / "post2-constrained-decoding/results" / f"{condition}__qwen.jsonl"
            rows = [json.loads(line) for line in path.read_text().splitlines()]
            self.assertEqual(len(rows), 640)
            self.assertEqual(len({(r["goal_id"], r["sample_idx"]) for r in rows}), 640)
            total = 0
            for r in rows:
                text = score.clean_output(r["text"])[0]
                ok = score.classify(text)[0] in ("named", "fallback")
                total += ok
                self.assertEqual(ok, audit.accepts(reduced, text))
            self.assertEqual(total, expected)


class RetryPolicy(unittest.TestCase):
    def client(self, outputs):
        self.calls = []
        outputs = iter(outputs)
        def create(**kwargs):
            self.calls.append(kwargs)
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=next(outputs)))])
        return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))

    def test_bounded_retries_and_punctuation(self):
        client = self.client(["", "simp;sorry", "rfl"])
        self.assertEqual(hardened_generate.hardened_chat(client, grammar="G", n=8), ("rfl", 3))
        self.assertTrue(all(c["n"] == 1 for c in self.calls))
        self.assertEqual(self.calls[0]["extra_body"]["guided_grammar"], "G")

    def test_exhaustion_is_explicit(self):
        with self.assertRaises(RuntimeError):
            hardened_generate.hardened_chat(self.client(["sorry", ""]), grammar="G", n_trials=2)

    def test_resume_does_not_skip_partial_goals_or_errors(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "run.jsonl"
            rows = [{"goal_id": 1, "sample_idx": 0, "text": "simp"},
                    {"goal_id": 1, "sample_idx": 1, "error": "timeout"},
                    {"goal_id": 2, "error": "legacy error without index"}]
            path.write_text("\n".join(map(json.dumps, rows))+"\n")
            self.assertEqual(gen_eval.completed_samples(path), {(1, 0)})


if __name__ == "__main__":
    unittest.main()
