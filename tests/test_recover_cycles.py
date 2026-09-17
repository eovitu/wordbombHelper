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


if __name__ == "__main__":
    unittest.main()
