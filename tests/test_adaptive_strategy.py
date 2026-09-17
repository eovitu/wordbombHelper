"""Testes da política adaptativa sem OCR, relógio ou estado global."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from application.adaptive_strategy import (  # noqa: E402
    AdaptiveStrategy,
    AdaptiveStrategyState,
    select_adaptive_candidate,
)


class AdaptiveStrategyTestCase(unittest.TestCase):
    def test_unmeasured_pressure_preserves_original_candidate_and_state(self):
        state = AdaptiveStrategyState(measured_decisions=4)

        result = select_adaptive_candidate(["muito-longa", "curta", "media"], None, state)

        self.assertEqual(result.candidate, "muito-longa")
        self.assertEqual(result.mode, "unmeasured")
        self.assertEqual(result.state, state)

    def test_low_pressure_interleaves_challenge_then_quick_deterministically(self):
        first = select_adaptive_candidate(["médio", "a", "bem-longa"], 0.10, AdaptiveStrategyState())
        second = select_adaptive_candidate(["médio", "a", "bem-longa"], 0.10, first.state)

        self.assertEqual((first.candidate, first.mode), ("bem-longa", "challenge"))
        self.assertEqual((second.candidate, second.mode), ("a", "quick"))
        self.assertEqual(second.state.measured_decisions, 2)

    def test_pressure_near_end_strongly_favors_shortest_candidate(self):
        result = select_adaptive_candidate(["original", "a", "longuíssima"], 0.90)

        self.assertEqual(result.candidate, "a")
        self.assertEqual(result.mode, "high_pressure_quick")

    def test_medium_pressure_also_uses_quick_candidate(self):
        result = select_adaptive_candidate(["original", "bb", "muito-longa"], 0.50)

        self.assertEqual(result.candidate, "bb")
        self.assertEqual(result.mode, "quick")

    def test_injected_state_adapter_is_reproducible(self):
        strategy = AdaptiveStrategy(AdaptiveStrategyState(measured_decisions=1))

        result = strategy.select(["longa", "x"], 0.20)

        self.assertEqual((result.candidate, result.mode), ("x", "quick"))
        self.assertEqual(strategy.state, result.state)

    def test_invalid_pressure_is_rejected(self):
        with self.assertRaises(ValueError):
            select_adaptive_candidate(["abc"], 1.1)
        with self.assertRaises(ValueError):
            select_adaptive_candidate(["abc"], True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
