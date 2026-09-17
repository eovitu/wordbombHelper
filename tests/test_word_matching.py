"""Testes da lógica pura de casamento de palavras do WordManager.

Cobre o coração do Pipeline B (`resolve_played_ocr`) e os helpers de normalização —
a regra "ZERO falso positivo" vira aqui uma propriedade EXECUTÁVEL em vez de aspiracional.

São testes puros (sem disco, sem OCR, sem hardware): injetamos uma wordlist em memória
e deixamos o código real construir os índices. Rode com:

    python -m unittest tests.test_word_matching
    # ou
    python tests/test_word_matching.py
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from word_manager import WordManager  # noqa: E402


def make_wm(words):
    """WordManager com uma wordlist 'test' injetada em memória (sem tocar o disco)."""
    wm = WordManager()
    wm.wordlists['test'] = {'lower': [w.lower() for w in words]}
    return wm


class TestNormalizeToken(unittest.TestCase):
    def test_lowercases_and_strips_accents(self):
        self.assertEqual(WordManager.normalize_token('PÁU'), 'pau')

    def test_keeps_hyphen_and_apostrophe(self):
        self.assertEqual(WordManager.normalize_token("PÁU-D'ALHO"), "pau-d'alho")

    def test_drops_digits_and_symbols(self):
        self.assertEqual(WordManager.normalize_token('a1b!c.'), 'abc')

    def test_empty_and_none(self):
        self.assertEqual(WordManager.normalize_token(''), '')
        self.assertEqual(WordManager.normalize_token(None), '')


class TestResolvePlayedOcr(unittest.TestCase):
    def test_exact_match_marks(self):
        wm = make_wm(['gato', 'cachorro'])
        status, canon = wm.resolve_played_ocr('gato', 'test')
        self.assertEqual(status, 'marked')
        self.assertEqual(canon, 'gato')
        self.assertIn('gato', wm.used_words)

    def test_accent_insensitive_exact_match(self):
        wm = make_wm(['avô'])
        status, canon = wm.resolve_played_ocr('avo', 'test')
        self.assertEqual(status, 'marked')
        self.assertEqual(canon, 'avô')  # devolve a forma REAL do dicionário
        self.assertIn('avô', wm.used_words)

    def test_proper_superset_is_ambiguous(self):
        # OCR pode ter cortado o fim: 'snowboard' tem superset 'snowboards' → não marca.
        wm = make_wm(['snowboard', 'snowboards'])
        status, canon = wm.resolve_played_ocr('snowboard', 'test')
        self.assertEqual(status, 'ambiguous')
        self.assertIsNone(canon)
        self.assertNotIn('snowboard', wm.used_words)

    def test_duplicate_clean_form_is_ambiguous(self):
        # 'avô' e 'avo' colapsam para o mesmo token limpo 'avo' → ambíguo, não marca.
        wm = make_wm(['avô', 'avo'])
        status, canon = wm.resolve_played_ocr('avo', 'test')
        self.assertEqual(status, 'ambiguous')
        self.assertIsNone(canon)

    def test_hamming1_unique_candidate_marks(self):
        # 'gxto' está a 1 substituição de 'gato' (único) → corrige e marca.
        wm = make_wm(['gato', 'casa'])
        status, canon = wm.resolve_played_ocr('gxto', 'test')
        self.assertEqual(status, 'marked')
        self.assertEqual(canon, 'gato')

    def test_hamming1_multiple_candidates_is_ambiguous(self):
        # 'xato' está a 1 substituição de 'gato' E de 'pato' → ambíguo, não marca.
        wm = make_wm(['gato', 'pato'])
        status, canon = wm.resolve_played_ocr('xato', 'test')
        self.assertEqual(status, 'ambiguous')
        self.assertIsNone(canon)

    def test_different_length_is_not_corrected(self):
        # Inserção/remoção (tamanho diferente) nunca é corrigida → unknown.
        wm = make_wm(['gato'])
        status, canon = wm.resolve_played_ocr('gatos', 'test')
        self.assertEqual(status, 'unknown')
        self.assertIsNone(canon)

    def test_completely_unknown_word(self):
        wm = make_wm(['gato'])
        status, canon = wm.resolve_played_ocr('zzzzzz', 'test')
        self.assertEqual(status, 'unknown')
        self.assertIsNone(canon)

    def test_too_short_is_unknown(self):
        wm = make_wm(['gato', 'oi'])
        status, _ = wm.resolve_played_ocr('a', 'test')
        self.assertEqual(status, 'unknown')

    def test_commit_is_idempotent(self):
        wm = make_wm(['gato'])
        wm.resolve_played_ocr('gato', 'test')
        before = len(wm.used_words)
        status, _ = wm.resolve_played_ocr('gato', 'test')
        self.assertEqual(status, 'marked')
        self.assertEqual(len(wm.used_words), before)  # não duplica


class TestApostropheCanonicalization(unittest.TestCase):
    def test_curly_apostrophe_maps_to_straight(self):
        self.assertEqual(WordManager.normalize_token("pa’u"), "pa'u")  # ’ curvo

    def test_left_curly_and_acute_and_backtick_map_to_straight(self):
        self.assertEqual(WordManager.normalize_token("d‘agua"), "d'agua")  # ‘
        self.assertEqual(WordManager.normalize_token("d´agua"), "d'agua")  # ´
        self.assertEqual(WordManager.normalize_token("d`agua"), "d'agua")  # `

    def test_straight_apostrophe_unchanged(self):
        self.assertEqual(WordManager.normalize_token("d'agua"), "d'agua")

    def test_ocr_curly_resolves_to_dict_word_with_straight(self):
        # Dicionário tem o reto; OCR leu o curvo → deve casar e marcar mesmo assim.
        wm = make_wm(["d'agua", "casa"])
        status, canon = wm.resolve_played_ocr("d’agua", "test")
        self.assertEqual(status, "marked")
        self.assertEqual(canon, "d'agua")


class TestPunctuationStripRecovery(unittest.TestCase):
    def test_dropped_hyphen_is_recovered(self):
        # OCR perdeu o hífen de "e-mail" → recupera pela forma só-letras.
        wm = make_wm(["e-mail", "casa"])
        status, canon = wm.resolve_played_ocr("email", "test")
        self.assertEqual(status, "marked")
        self.assertEqual(canon, "e-mail")

    def test_dropped_apostrophe_is_recovered(self):
        wm = make_wm(["d'agua", "casa"])
        status, canon = wm.resolve_played_ocr("dagua", "test")
        self.assertEqual(status, "marked")
        self.assertEqual(canon, "d'agua")

    def test_alpha_collision_is_ambiguous_not_false_positive(self):
        # Duas palavras reais que só diferem na pontuação → forma só-letras é ambígua.
        wm = make_wm(["re-tratar", "retra-tar"])
        status, canon = wm.resolve_played_ocr("retratar", "test")
        self.assertEqual(status, "ambiguous")
        self.assertIsNone(canon)
        self.assertNotIn("re-tratar", wm.used_words)
        self.assertNotIn("retra-tar", wm.used_words)

    def test_hyphenated_exact_still_marks(self):
        wm = make_wm(["pau-d'alho", "casa"])
        status, canon = wm.resolve_played_ocr("pau-d'alho", "test")
        self.assertEqual(status, "marked")
        self.assertEqual(canon, "pau-d'alho")

    def test_curly_apostrophe_hyphenated_word(self):
        wm = make_wm(["pau-d'alho"])
        status, canon = wm.resolve_played_ocr("pau-d’alho", "test")  # apóstrofe curvo
        self.assertEqual(status, "marked")
        self.assertEqual(canon, "pau-d'alho")

    def test_plain_word_unaffected_by_recovery(self):
        wm = make_wm(["casa", "gato"])
        status, canon = wm.resolve_played_ocr("casa", "test")
        self.assertEqual(status, "marked")
        self.assertEqual(canon, "casa")

    def test_genuinely_unknown_stays_unknown(self):
        # Letras diferentes (não só pontuação) não devem ser recuperadas.
        wm = make_wm(["casa", "e-mail"])
        status, _ = wm.resolve_played_ocr("zzzzzz", "test")
        self.assertEqual(status, "unknown")


class TestHammingHelpers(unittest.TestCase):
    def test_unique_hamming1_returns_single(self):
        self.assertEqual(WordManager._unique_hamming1('gxto', ['gato', 'casa']), 'gato')

    def test_unique_hamming1_none_when_multiple(self):
        self.assertIsNone(WordManager._unique_hamming1('xato', ['gato', 'pato']))

    def test_unique_hamming1_none_when_zero(self):
        self.assertIsNone(WordManager._unique_hamming1('zzzz', ['gato']))

    def test_has_proper_superset(self):
        keys = sorted(['snowboard', 'snowboards', 'casa'])
        self.assertTrue(WordManager._has_proper_superset('snowboard', keys))
        self.assertFalse(WordManager._has_proper_superset('casa', keys))


if __name__ == '__main__':
    unittest.main(verbosity=2)
