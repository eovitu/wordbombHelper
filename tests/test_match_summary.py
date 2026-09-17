"""Testes do resumo de partida baseado somente em eventos confirmados.

Rode com: python -m unittest tests.test_match_summary
"""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from application.match_summary import MatchSummary, MatchSummaryError  # noqa: E402


class TestMatchSummary(unittest.TestCase):
    def setUp(self):
        self.timestamps = iter([100.25, 101.5, 102.75, 104.0])
        self.summary = MatchSummary(clock=lambda: next(self.timestamps))

    def test_empty_snapshot_has_no_inferred_words_or_events(self):
        self.assertEqual(
            self.summary.snapshot(),
            {
                "confirmed_words": 0,
                "missing_prompts": 0,
                "rejections": 0,
                "learned_words": 0,
                "event_count": 0,
                "retained_event_count": 0,
                "events": [],
            },
        )

    def test_explicit_event_methods_record_only_their_confirmed_event(self):
        confirmed = self.summary.record_confirmed_word("CAS", "Casa", "turn_end")
        missing = self.summary.record_missing_prompt("xyz")
        rejected = self.summary.record_rejection("gat", "gato")
        learned = self.summary.record_learned_word("Árvore", "solve_ocr")

        snapshot = self.summary.snapshot()
        self.assertEqual(confirmed, {"id": 1, "type": "confirmed_word", "timestamp": 100.25,
                                     "prompt": "cas", "word": "casa", "source": "turn_end"})
        self.assertEqual(missing["type"], "missing_prompt")
        self.assertEqual(rejected["type"], "rejection")
        self.assertEqual(learned["word"], "árvore")
        self.assertEqual(snapshot["confirmed_words"], 1)
        self.assertEqual(snapshot["missing_prompts"], 1)
        self.assertEqual(snapshot["rejections"], 1)
        self.assertEqual(snapshot["learned_words"], 1)
        self.assertEqual(snapshot["event_count"], 4)
        self.assertEqual(snapshot["retained_event_count"], 4)
        json.dumps(snapshot)

    def test_event_log_is_capped_but_total_counts_are_not(self):
        summary = MatchSummary(max_events=2, clock=lambda: 1)
        summary.record_missing_prompt("ab")
        summary.record_missing_prompt("cd")
        summary.record_missing_prompt("ef")

        snapshot = summary.snapshot()
        self.assertEqual(snapshot["missing_prompts"], 3)
        self.assertEqual(snapshot["event_count"], 3)
        self.assertEqual(snapshot["retained_event_count"], 2)
        self.assertEqual([event["prompt"] for event in snapshot["events"]], ["cd", "ef"])
        self.assertEqual([event["id"] for event in snapshot["events"]], [2, 3])

    def test_reset_returns_the_previous_snapshot_then_starts_a_new_match(self):
        self.summary.record_confirmed_word("cas", "casa", "turn_end")
        previous = self.summary.reset()

        self.assertEqual(previous["confirmed_words"], 1)
        self.assertEqual(previous["events"][0]["word"], "casa")
        self.assertEqual(self.summary.snapshot()["event_count"], 0)
        fresh = self.summary.record_missing_prompt("zz")
        self.assertEqual(fresh["id"], 1)

    def test_snapshot_is_a_copy_not_a_reference_to_internal_events(self):
        self.summary.record_missing_prompt("ab")
        snapshot = self.summary.snapshot()
        snapshot["events"][0]["prompt"] = "changed"
        self.assertEqual(self.summary.snapshot()["events"][0]["prompt"], "ab")

    def test_invalid_fields_and_invalid_cap_are_rejected(self):
        with self.assertRaises(MatchSummaryError):
            MatchSummary(max_events=0)
        with self.assertRaises(MatchSummaryError):
            self.summary.record_confirmed_word("two words", "casa", "turn_end")
        with self.assertRaises(MatchSummaryError):
            self.summary.record_learned_word("casa", "")


if __name__ == "__main__":
    unittest.main(verbosity=2)
