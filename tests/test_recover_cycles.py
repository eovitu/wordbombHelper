import unittest

from word_manager import WordManager


class RecoverCycleTests(unittest.TestCase):
    def complete_cycle(self, manager):
        manager.mark_used("abcdefghijlmnopqrstuvxz")

    def test_casual_targets_are_one_then_two_and_exclude_kwy(self):
        manager = WordManager()
        manager.configure_recover("casual")
        self.assertEqual(1, manager.recover_progress()["target"])
        self.assertTrue({"k", "w", "y"}.isdisjoint(manager.letter_targets))
        self.complete_cycle(manager)
        self.assertEqual(2, manager.recover_progress()["target"])

    def test_ranked_targets_are_three_four_then_five(self):
        manager = WordManager()
        manager.configure_recover("ranked")
        self.assertEqual(3, manager.recover_progress()["target"])
        for cycle, target in enumerate((4, 5, 5), start=1):
            for index in range(manager.recover_target):
                manager.mark_used("abcdefghijlmnopqrstuvxz" + str(cycle) + str(index))
            self.assertEqual(target, manager.recover_progress()["target"])

    def test_opponent_word_can_be_unavailable_without_advancing_recover(self):
        manager = WordManager()
        before = manager.recover_progress()
        manager.mark_unavailable("casa")
        self.assertIn("casa", manager.used_words)
        self.assertEqual(before, manager.recover_progress())

    def test_length_preference_follows_match_speed_bands(self):
        manager = WordManager()

        expected = {
            24: None,
            25: 40,
            39: 40,
            40: 35,
            50: 25,
            70: 20,
            100: 15,
            150: 15,
        }
        for played, preferred_max in expected.items():
            manager.confirmed_word_count = played
            self.assertEqual(preferred_max, manager.recover_progress()["preferred_max_length"])

    def test_late_recover_prefers_short_helpful_word(self):
        manager = WordManager()
        manager.confirmed_word_count = 80
        manager.letter_targets = {"a": 1, "b": 1, "c": 1}

        picked = manager._pick_locked(
            ["abc-muito-comprida", "abacaxi", "cabana-curta"],
            False, "recover", "", "")

        self.assertEqual("abacaxi", picked)

    def test_late_recover_uses_shortest_helpful_fallback_without_hard_limit(self):
        manager = WordManager()
        manager.confirmed_word_count = 80
        manager.letter_targets = {"z": 1}

        picked = manager._pick_locked(
            ["z" + ("a" * 25), "z" + ("b" * 22)],
            False, "recover", "", "")

        self.assertEqual("z" + ("b" * 22), picked)

    def test_after_one_hundred_fifty_words_recover_prefers_fast_efficiency(self):
        manager = WordManager()
        manager.confirmed_word_count = 150
        manager.letter_targets = {"a": 1, "b": 1, "c": 1, "d": 1}

        picked = manager._pick_locked(
            ["abcdefghijkl", "abcde", "abzzzzzz"],
            False, "recover", "", "")

        self.assertEqual("abcde", picked)
        self.assertTrue(manager.recover_progress()["fast_strategic"])


if __name__ == "__main__":
    unittest.main()
