"""Testes da montagem da sílaba a partir dos tokens do OCR (ScreenReader).

Reproduzem os casos REAIS observados no log onde o apóstrofe da borda era perdido ou
duplicado: 'AL → 'al, D' → d', D'' → d'. Tokens são (clean_upper, conf, height, top, left).

Rode com: python -m unittest tests.test_prompt_assembly
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from screen_reader import ScreenReader  # noqa: E402

MIN_H, MIN_LEN, MAX_LEN = 35, 1, 6
UI = {"SUA", "VEZ", "SUAVEZ", "YOUR", "TURN", "YOURTURN"}


def sel(tokens):
    return ScreenReader._select_prompt_from_tokens(tokens, MIN_H, MIN_LEN, MAX_LEN, UI)


class TestCollapseApostropheDups(unittest.TestCase):
    def test_double_apostrophe_collapses(self):
        self.assertEqual(ScreenReader._collapse_apos_dups("D''"), "D'")

    def test_double_hyphen_collapses(self):
        self.assertEqual(ScreenReader._collapse_apos_dups("A--B"), "A-B")

    def test_single_punct_unchanged(self):
        self.assertEqual(ScreenReader._collapse_apos_dups("D'AGUA"), "D'AGUA")
        self.assertEqual(ScreenReader._collapse_apos_dups("PAU-D'ARCO"), "PAU-D'ARCO")


class TestPromptAssembly(unittest.TestCase):
    def test_single_letter_prompt_is_accepted(self):
        cand, _ = sel([("I", 88, 40, 100, 200)])
        self.assertEqual(cand, "i")

    def test_plain_single_token_unchanged(self):
        # Caso comum: prompt simples 'nfl' lido como 1 token → inalterado.
        cand, conf = sel([("NFL", 88, 60, 100, 200)])
        self.assertEqual(cand, "nfl")
        self.assertEqual(conf, 88)

    def test_leading_apostrophe_split_is_reassembled(self):
        # LOG REAL: 'AL lido como ' (baixo) + AL → antes virava 'al' perdendo o apóstrofe.
        cand, _ = sel([("'", 70, 24, 108, 180), ("AL", 85, 60, 100, 205)])
        self.assertEqual(cand, "'al")

    def test_trailing_apostrophe_split_is_reassembled(self):
        # LOG REAL: D' lido como D + ' → d'
        cand, _ = sel([("D", 85, 60, 100, 200), ("'", 70, 24, 108, 240)])
        self.assertEqual(cand, "d'")

    def test_doubled_apostrophe_is_collapsed(self):
        # LOG REAL: D' virou d'' (cursor lido como apóstrofe extra) → colapsa para d'
        cand, _ = sel([("D", 85, 60, 100, 200), ("'", 70, 24, 108, 240),
                       ("'", 55, 22, 108, 255)])
        self.assertEqual(cand, "d'")

    def test_hyphen_prompt_single_token(self):
        cand, _ = sel([("X-A", 84, 60, 100, 200)])
        self.assertEqual(cand, "x-a")

    def test_sua_vez_is_ignored(self):
        # "SUA"/"VEZ" (UI) na região não devem entrar na sílaba.
        cand, _ = sel([("'", 70, 24, 108, 180), ("AL", 85, 60, 100, 205),
                       ("SUA", 90, 18, 175, 760), ("VEZ", 90, 18, 175, 800)])
        self.assertEqual(cand, "'al")

    def test_typed_word_tiles_below_are_ignored(self):
        # Os tiles da palavra digitada ficam BEM abaixo (top grande) → fora da linha.
        cand, _ = sel([("AL", 85, 60, 100, 205),
                       ("D", 80, 55, 400, 560), ("EMBER", 80, 55, 400, 620)])
        self.assertEqual(cand, "al")

    def test_no_alpha_anchor_returns_empty(self):
        # Só um apóstrofe solto, sem letras → não é sílaba válida.
        cand, conf = sel([("'", 70, 24, 108, 180)])
        self.assertEqual(cand, "")
        self.assertEqual(conf, -1.0)

    def test_short_alpha_noise_not_merged(self):
        # Um 'i' baixinho (ruído, height < 0.6*anchor) longe não deve grudar na sílaba.
        cand, _ = sel([("AL", 85, 60, 100, 205), ("I", 40, 15, 110, 120)])
        self.assertEqual(cand, "al")

    def test_alphabetic_token_on_next_visual_line_is_not_joined(self):
        cand, _ = sel([("IS", 88, 40, 0, 200), ("CC", 86, 30, 40, 205)])

        self.assertEqual(cand, "is")


if __name__ == "__main__":
    unittest.main(verbosity=2)
