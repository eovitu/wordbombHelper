import unittest

from application.word_service import SuggestionSession, WordService
from used_word_scanner import UsedWordScanner


class FakeManager:
    def __init__(self):
        self.used = []
        self.rejected = []
        self.current_language = "Português"

    def configure_recover(self, mode, exclude):
        pass

    def get_candidates(self, prompt, *args, **kwargs):
        return {"ca": ["casa", "caju", "cavalo"], "ga": ["gato"]}.get(prompt, [])

    def mark_used(self, word):
        self.used.append(word)

    def normalize_token(self, word):
        return word.lower()

    def confirm_own_word(self, word):
        self.used.append(word)

    def reject_word(self, word):
        self.rejected.append(word)

    def reset_used(self):
        pass


class FakeReader:
    suggested_word = ""
    suggestion_index = 0
    suggestion_total = 0
    last_suggested_prompt = ""
    preview_prompt = ""
    last_word_typed = ""

    def override_prompt(self, prompt):
        self.preview_prompt = prompt


class FakeState:
    def __init__(self):
        self.logs = []

    def snapshot_config(self):
        return {"lang": "Português", "min_len": 1, "max_len": 46,
                "strategy": "random", "recover_mode": "casual",
                "recover_exclude": "", "auto_type": False}

    def add_log(self, message):
        self.logs.append(message)


class FakeTyper:
    pass


class SuggestionLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.manager = FakeManager()
        self.reader = FakeReader()
        self.service = WordService(self.manager, FakeTyper(), self.reader, FakeState())

    def test_explosion_does_not_consume_suggestion(self):
        self.service.on_prompt_found("ca")
        self.assertEqual([], self.manager.used)
        self.service.finish_turn()
        self.assertEqual([], self.manager.used)

    def test_green_suggestion_is_confirmed_when_turn_finishes(self):
        self.service.on_prompt_found("ca")
        self.assertTrue(self.service.observe_accepted_word("casa"))
        self.assertEqual([], self.manager.used)
        self.service.finish_turn()
        self.assertEqual(["casa"], self.manager.used)

    def test_green_alternative_after_invalid_attempt_counts_actual_word(self):
        self.service.on_prompt_found("ca")
        self.assertFalse(self.service.observe_accepted_word("gato"))
        self.assertTrue(self.service.observe_accepted_word("caju"))
        self.service.finish_turn()
        self.assertEqual(["caju"], self.manager.used)

    def test_scanner_green_alternative_confirms_service_after_red_attempt(self):
        class Source:
            def poll(self):
                return ["CAJU"]  # A máscara da fonte descarta tentativas vermelhas.

        self.manager.resolve_played_ocr = lambda raw, lang, count_recover=False: ("marked", raw.lower())
        scanner = UsedWordScanner(
            self.manager, Source(), lambda: "Português",
            on_accepted_word=self.service.observe_accepted_word,
        )
        self.service.on_prompt_found("ca")
        scanner._scan_and_learn()
        self.service.finish_turn()
        self.assertEqual(["caju"], self.manager.used)
        self.assertEqual(0, scanner.learned_count)

    def test_same_prompt_retry_does_not_delete_dictionary_word(self):
        self.service.on_prompt_found("ca")
        self.service.on_prompt_found("ca")
        self.assertEqual([], self.manager.rejected)
        self.assertEqual([], self.manager.used)
        self.assertEqual("caju", self.reader.suggested_word)
        self.assertTrue(self.service.on_prompt_found("ca"))
        self.assertEqual("cavalo", self.reader.suggested_word)
        self.assertFalse(self.service.on_prompt_found("ca"))

    def test_green_from_other_prompt_does_not_confirm_explosion(self):
        self.service.on_prompt_found("ca")
        self.assertFalse(self.service.observe_accepted_word("gato"))
        self.service.finish_turn()
        self.assertEqual([], self.manager.used)

    def test_late_green_after_turn_end_cannot_be_attributed_to_previous_turn(self):
        self.service.on_prompt_found("ca")
        self.service.finish_turn()
        self.assertFalse(self.service.observe_accepted_word("casa"))
        self.assertEqual([], self.manager.used)

    def test_manual_correction_does_not_consume_wrong_suggestion(self):
        self.service.on_prompt_found("ca")
        result = self.service.correct_prompt("ga")
        self.assertEqual("gato", result["word"])
        self.assertEqual([], self.manager.used)

    def test_reject_excludes_word_without_confirming_it(self):
        self.service.on_prompt_found("ca")
        result = self.service.reject_current()
        self.assertEqual(["casa"], self.manager.rejected)
        self.assertEqual([], self.manager.used)
        self.assertEqual("caju", result["word"])
        self.assertEqual(self.service.action_notice, "CASA foi removida do dicionário.")

    def test_short_reroll_selects_shortest_unseen_alternative(self):
        session = SuggestionSession("x", ["comprida", "media", "oi", "curta"])
        self.service._set_session(session)
        self.assertEqual("oi", self.service.reroll_short()["word"])
        self.assertEqual("media", self.service.reroll_short()["word"])


if __name__ == "__main__":
    unittest.main()
