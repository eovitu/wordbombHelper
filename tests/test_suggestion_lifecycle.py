import unittest

from application.word_service import SuggestionSession, WordService


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

    def test_suggestion_is_confirmed_only_when_turn_finishes(self):
        self.service.on_prompt_found("ca")
        self.assertEqual([], self.manager.used)
        self.service.finish_turn()
        self.assertEqual(["casa"], self.manager.used)

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
