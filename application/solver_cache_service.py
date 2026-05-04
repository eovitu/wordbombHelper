import logging
import threading

from letter_link_solver import LetterLinkSolver

logger = logging.getLogger(__name__)


class SolverCacheService:
    def __init__(self, word_manager):
        self.word_manager = word_manager
        self._cache = {}
        self._lock = threading.RLock()

    def build_trie_bg(self, lang=None):
        if lang is None:
            lang = self.word_manager.current_language

        if hasattr(self.word_manager, "_resolve_language_name"):
            lang = self.word_manager._resolve_language_name(lang)

        # Ensure the language is loaded
        if lang not in self.word_manager.wordlists:
            self.word_manager._load_language(lang)

        if lang not in self.word_manager.wordlists:
            logger.error("Language '%s' not found in wordlists!", lang)
            return None

        with self._lock:
            if lang in self._cache:
                return self._cache[lang]

            wordlist = self.word_manager.wordlists[lang]["full"]
            logger.info("Building Letter Link Trie from %s (%s words)...", lang, len(wordlist))

            solver = LetterLinkSolver()
            count = solver.build_trie_from_list(wordlist)
            self._cache[lang] = solver

            logger.info("Trie complete: %s words indexed for Letter Link.", count)
            return solver

    def get_or_build_solver(self, lang):
        return self.build_trie_bg(lang=lang)

    def clear(self):
        with self._lock:
            self._cache.clear()
