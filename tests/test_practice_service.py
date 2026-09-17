"""Testes puros do modo offline de prática.

Rode com: python -m unittest tests.test_practice_service
"""
import os
import random
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from application.practice_service import (  # noqa: E402
    NoPracticeWordsError,
    PracticeRound,
    PracticeService,
)
from word_manager import WordManager  # noqa: E402


def make_word_manager(words):
    manager = WordManager()
    lower = [word.lower() for word in words]
    manager.wordlists["test"] = {
        "full": list(words),
        "lower": lower,
        "len_map": {},
    }
    return manager


class RecordingRandom:
    def __init__(self):
        self.last_population = ()
        self.last_weights = ()

    def choices(self, population, weights, k):
        self.last_population = tuple(population)
        self.last_weights = tuple(weights)
        return [population[0]]

    def choice(self, values):
        return values[0]


class TestPracticeService(unittest.TestCase):
    def setUp(self):
        self.manager = make_word_manager(["casa", "casar", "gato", "e-mail"])
        self.service = PracticeService(self.manager, random_source=random.Random(4), slow_response_seconds=3)

    def test_generated_prompt_and_answer_belong_to_the_active_dictionary(self):
        round_ = self.service.generate_round("test", min_prompt_length=2, max_prompt_length=2)
        self.assertIn(round_.answer, self.manager.wordlists["test"]["full"])
        self.assertIn(round_.prompt, round_.answer.casefold())
        self.assertEqual(round_.language, "test")

    def test_evaluation_accepts_any_active_dictionary_word_that_contains_the_prompt(self):
        result = self.service.evaluate(PracticeRound("test", "cas", "casa"), "CASAR", elapsed_seconds=1.5)
        self.assertTrue(result.correct)
        self.assertEqual(result.reason, "correct")
        self.assertEqual(result.word, "casar")
        self.assertEqual(result.elapsed_seconds, 1.5)

    def test_evaluation_distinguishes_missing_prompt_and_unknown_word(self):
        round_ = PracticeRound("test", "cas", "casa")
        missing_prompt = self.service.evaluate(round_, "gato")
        unknown = self.service.evaluate(round_, "casinha")
        self.assertEqual(missing_prompt.reason, "missing_prompt")
        self.assertEqual(unknown.reason, "not_in_dictionary")

    def test_practice_never_changes_used_or_rejected_game_state(self):
        self.manager.used_words.add("gato")
        self.manager.rejected_words.add("casa")
        used_before = set(self.manager.used_words)
        rejected_before = set(self.manager.rejected_words)

        round_ = self.service.generate_round("test", min_prompt_length=2, max_prompt_length=2)
        self.service.evaluate(round_, "resposta-inválida", elapsed_seconds=4)

        self.assertEqual(self.manager.used_words, used_before)
        self.assertEqual(self.manager.rejected_words, rejected_before)

    def test_hints_are_progressive_and_do_not_require_a_new_round(self):
        round_ = PracticeRound("test", "cas", "casa")
        self.assertEqual(self.service.hint(round_, "length").value, 4)
        self.assertEqual(self.service.hint(round_, "first_letter").value, "c")
        self.assertEqual(self.service.hint(round_, "answer").value, "casa")

    def test_error_and_slow_correct_answer_raise_future_prompt_weight(self):
        source = RecordingRandom()
        service = PracticeService(self.manager, random_source=source, slow_response_seconds=3)
        difficult = PracticeRound("test", "ca", "casa")
        service.evaluate(difficult, "gato")
        service.evaluate(difficult, "casa", elapsed_seconds=3)

        stats = service.get_prompt_stats("test", "ca")
        service.generate_round("test", min_prompt_length=2, max_prompt_length=2)
        ca_weight = source.last_weights[source.last_population.index("ca")]

        self.assertEqual(stats.attempts, 2)
        self.assertEqual(stats.errors, 1)
        self.assertEqual(stats.slow_responses, 1)
        self.assertEqual(ca_weight, 5)  # base 1 + erro*3 + lento*1

    def test_empty_or_unknown_language_has_no_round(self):
        with self.assertRaises(NoPracticeWordsError):
            self.service.generate_round("missing")


if __name__ == "__main__":
    unittest.main(verbosity=2)
