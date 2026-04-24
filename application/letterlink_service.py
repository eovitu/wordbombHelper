import logging

import numpy as np

logger = logging.getLogger(__name__)


class LetterLinkService:
    def __init__(self, grid_reader, screen_reader, solver_cache, region_store):
        self.grid_reader = grid_reader
        self.screen_reader = screen_reader
        self.solver_cache = solver_cache
        self.region_store = region_store

    def solve(self):
        region = self.region_store.get_region() or self.screen_reader.turn_region
        if not region:
            return {"status": "error", "message": "Calibrate grid first"}, 200

        matrix, _coords = self.grid_reader.read_grid(region)
        if not matrix:
            return {"status": "error", "message": "Failed to read grid. Check Tesseract."}, 200

        logger.info("Grid read: %s", np.array(matrix))

        logger.info("Fetching cached Trie for Portugues...")
        solver = self.solver_cache.get_or_build_solver("Portugues")
        if not solver:
            return {"status": "error", "message": "Failed to initialize Portuguese trie"}, 500

        logger.info("Solving grid with Trie (root has %s children)...", len(solver.trie.root.children))
        results = solver.solve_grid(matrix)
        logger.info("Found %s words total", len(results))

        if not results:
            return {"status": "error", "message": "No words found in Portuguese wordlist. Check grid OCR!"}, 200

        top_words = [{"word": word, "score": score, "path": path} for word, path, score in results[:5]]
        best_word = top_words[0]

        logger.info("Letter Link -> Best: '%s' (%s pts)", best_word["word"], best_word["score"])
        top_5_words = ", ".join(f"{w['word']}({w['score']}pts)" for w in top_words)
        logger.info("Top 5: %s", top_5_words)

        return {
            "status": "success",
            "word": best_word["word"],
            "score": best_word["score"],
            "top_words": top_words,
            "matrix": matrix,
        }, 200
