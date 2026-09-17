"""Testes do armazenamento isolado de palavras pessoais.

Rode com: python -m unittest tests.test_personal_dictionary
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from application.personal_dictionary import (  # noqa: E402
    ImportPreview,
    NotFoundError,
    PersonalDictionary,
    UndoUnavailableError,
    ValidationError,
)


class PersonalDictionaryTestCase(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.storage = Path(self.tempdir.name) / "personal_wordlists"
        self.dictionary = PersonalDictionary(self.storage)

    def tearDown(self):
        self.tempdir.cleanup()

    def test_add_persists_utf8_and_exposes_words_for_later_word_manager_merge(self):
        self.assertEqual(self.dictionary.add("Português", "Árvore"), "árvore")
        self.assertEqual(self.dictionary.get_words("Português"), ["árvore"])
        self.assertEqual((self.storage / "Português.txt").read_text(encoding="utf-8"), "árvore\n")

    def test_add_rejects_duplicates_without_rewriting_the_list(self):
        self.dictionary.add("Inglês", "e-mail")
        with self.assertRaises(ValidationError):
            self.dictionary.add("Inglês", "E-MAIL")
        self.assertEqual(self.dictionary.get_words("Inglês"), ["e-mail"])

    def test_edit_replaces_in_place_and_delete_removes_word(self):
        self.dictionary.add("Português", "casa")
        self.dictionary.add("Português", "gato")
        self.assertEqual(self.dictionary.edit("Português", "casa", "lar"), "lar")
        self.dictionary.delete("Português", "gato")
        self.assertEqual(self.dictionary.get_words("Português"), ["lar"])

    def test_prepend_places_automatic_word_at_top(self):
        self.dictionary.add("Português", "antiga")

        self.dictionary.prepend("Português", "NOVA")

        self.assertEqual(self.dictionary.get_words("Português"), ["nova", "antiga"])

    def test_edit_and_delete_missing_word_raise_not_found(self):
        with self.assertRaises(NotFoundError):
            self.dictionary.edit("Português", "ausente", "nova")
        with self.assertRaises(NotFoundError):
            self.dictionary.delete("Português", "ausente")

    def test_word_validation_requires_one_word_per_line(self):
        invalid = ["", " casa", "casa ", "duas palavras", "casa\ngato", "a1", "---"]
        for word in invalid:
            with self.subTest(word=word):
                with self.assertRaises(ValidationError):
                    self.dictionary.add("Português", word)
        self.assertEqual(self.dictionary.get_words("Português"), [])

    def test_language_cannot_escape_the_personal_dictionary_directory(self):
        for language in ("../wordlists", "C:temp", "Português "):
            with self.subTest(language=language):
                with self.assertRaises(ValidationError):
                    self.dictionary.add(language, "casa")

    def test_preview_import_separates_new_duplicate_and_invalid_lines(self):
        self.dictionary.add("Português", "casa")
        preview = self.dictionary.preview_import("Português", "Gato\ncasa\nGATO\nduas\ninválida1\n")
        self.assertEqual(preview.new_words, ("gato", "duas"))
        self.assertEqual(preview.duplicates, ((2, "casa"), (3, "gato")))
        self.assertEqual(preview.invalid_lines[0][0:2], (5, "inválida1"))
        self.assertEqual(self.dictionary.get_words("Português"), ["casa"])

    def test_preview_import_accepts_words_separated_by_spaces(self):
        preview = self.dictionary.preview_import(
            "Português", "ENRUDECA ENRUDECAIS ENRUDECAM ENRUDECAMOS ENRUDECAS"
        )
        self.assertEqual(
            preview.new_words,
            ("enrudeca", "enrudecais", "enrudecam", "enrudecamos", "enrudecas"),
        )
        self.assertEqual(preview.invalid_lines, ())

    def test_apply_import_is_atomic_when_preview_has_invalid_lines(self):
        preview = self.dictionary.preview_import("Português", "casa\nerrada1\ngato")
        with self.assertRaises(ValidationError):
            self.dictionary.apply_import(preview)
        self.assertEqual(self.dictionary.get_words("Português"), [])

    def test_apply_import_adds_unique_words_as_single_batch(self):
        preview = self.dictionary.preview_import("Português", "casa\ngato\ncasa\n")
        self.assertEqual(self.dictionary.apply_import(preview), ["casa", "gato"])
        self.assertEqual(self.dictionary.get_words("Português"), ["casa", "gato"])

    def test_undo_restores_most_recent_batch_and_is_available_after_reopen(self):
        preview = self.dictionary.preview_import("Português", "casa\ngato")
        self.dictionary.apply_import(preview)

        reopened = PersonalDictionary(self.storage)
        result = reopened.undo()

        self.assertEqual(result["operation"], "import")
        self.assertEqual(result["language"], "Português")
        self.assertEqual(result["words"], [])
        self.assertEqual(reopened.get_words("Português"), [])
        with self.assertRaises(UndoUnavailableError):
            reopened.undo()

    def test_latest_mutation_replaces_previous_undo_record(self):
        self.dictionary.add("Português", "casa")
        self.dictionary.add("Português", "gato")
        self.dictionary.undo()
        self.assertEqual(self.dictionary.get_words("Português"), ["casa"])

    def test_files_are_written_without_leftover_temporary_files(self):
        self.dictionary.add("Português", "casa")
        self.assertEqual(sorted(path.name for path in self.storage.iterdir()), [".last_undo.json", "Português.txt"])

    def test_apply_import_revalidates_a_manually_constructed_preview(self):
        unsafe_preview = ImportPreview("Português", ("casa", "duas palavras"), (), ())
        with self.assertRaises(ValidationError):
            self.dictionary.apply_import(unsafe_preview)
        self.assertEqual(self.dictionary.get_words("Português"), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
