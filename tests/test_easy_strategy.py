import unittest

from word_manager import WordManager


class EasyStrategyTests(unittest.TestCase):
    def setUp(self):
        self.manager = WordManager()

    def pick(self, words):
        return self.manager._pick_locked(words, False, "easy", "", "")

    def test_prefers_plain_word_over_punctuation_and_accents(self):
        self.assertEqual("panela", self.pick(["pão-d'alho", "panela"]))

    def test_penalizes_hard_consonant_clusters(self):
        self.assertEqual("casario", self.pick(["krysztof", "casario"]))

    def test_uses_length_then_alphabetical_order_as_stable_tiebreakers(self):
        self.assertEqual("casa", self.pick(["mesa", "casa", "casaco"]))


if __name__ == "__main__":
    unittest.main()
