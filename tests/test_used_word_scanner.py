import unittest

import numpy as np

from used_word_scanner import OcrSolvePanelSource, UsedWordScanner


class FakeSource:
    def poll(self):
        return ["EEEEE"]


class FakeWordManager:
    @staticmethod
    def normalize_token(value):
        return value.lower()

    @staticmethod
    def resolve_played_ocr(raw, lang, count_recover=False):
        return "unknown", None

    def refresh_language(self, lang):
        pass

    def mark_unavailable(self, word):
        pass


class FakeDictionary:
    def __init__(self):
        self.added = []

    def prepend(self, lang, word):
        self.added.append((lang, word))
        return word.lower()


class FakeReviewStore:
    def __init__(self):
        self.recorded = []

    def record(self, value):
        self.recorded.append(value)


class UsedWordScannerSafetyTests(unittest.TestCase):
    def test_red_text_cannot_enter_green_word_pipeline(self):
        class Region:
            def get_region(self):
                return {"x1": 0, "y1": 0, "width": 40, "height": 20}

        class Capture:
            def __init__(self, color):
                frame = np.full((20, 40, 4), 255, dtype=np.uint8)
                frame[:, :, :3] = color
                self.raw = frame.tobytes()
                self.width = 40
                self.height = 20

        class Grabber:
            def __init__(self, color):
                self.color = color

            def grab(self, monitor):
                return Capture(self.color)

        class Engine:
            calls = 0

            def read_tokens(self, image):
                self.calls += 1
                return [("CASA", 90, 0, 0)]

        source = OcrSolvePanelSource(Region(), "", "")
        source._engine_ok = True
        source._engine = Engine()
        source._sct = Grabber((0, 0, 255))  # BGR vermelho
        self.assertEqual([], source.poll())
        self.assertEqual(0, source._engine.calls)
        source._sct = Grabber((0, 255, 0))  # BGR verde
        self.assertEqual(["CASA"], source.poll())
        self.assertEqual(1, source._engine.calls)

    def test_green_own_word_is_not_logged_as_opponent_learning(self):
        class KnownManager(FakeWordManager):
            @staticmethod
            def resolve_played_ocr(raw, lang, count_recover=False):
                return "marked", raw.lower()

        observed = []
        scanner = UsedWordScanner(
            KnownManager(), FakeSource(), lambda: "Português",
            on_accepted_word=lambda word: observed.append(word) or True,
        )
        scanner._scan_and_learn()
        scanner._scan_and_learn()
        self.assertEqual(["eeeee"], observed)
        self.assertEqual(0, scanner.learned_count)
        self.assertEqual([], scanner.learned_log())

    def test_repeated_unknown_ocr_is_added_through_prepend_for_easy_review(self):
        dictionary = FakeDictionary()
        review = FakeReviewStore()
        scanner = UsedWordScanner(
            FakeWordManager(), FakeSource(), lambda: "Português",
            personal_dictionary=dictionary, ambiguous_store=review,
        )

        for _ in range(3):
            scanner._scan_and_learn()

        self.assertEqual(dictionary.added, [("Português", "EEEEE")])
        self.assertEqual(review.recorded, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
