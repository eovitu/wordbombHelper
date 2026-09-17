import tempfile
import unittest
from pathlib import Path

from word_manager import WordManager


class PermanentRejectionTests(unittest.TestCase):
    def test_reject_removes_word_from_active_language_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "Português.txt"
            path.write_text("bombea\ncasa\nmou\n", encoding="utf-8")
            manager = WordManager(wordlist_dir=directory)
            manager.current_language = "Português"

            manager.reject_word("mou")

            self.assertEqual(path.read_text(encoding="utf-8"), "bombea\ncasa\n")
            self.assertNotIn("mou", manager.get_candidates("mou", "Português", 1, 46, "random"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
