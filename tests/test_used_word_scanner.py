import unittest

from used_word_scanner import UsedWordScanner


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
