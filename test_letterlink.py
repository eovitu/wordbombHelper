#!/usr/bin/env python
"""Quick test of Letter Link solver with Portuguese wordlist"""

from word_manager import WordManager
from letter_link_solver import LetterLinkSolver
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load wordlists
wm = WordManager()
logger.info(f"Available languages: {wm.get_languages()}")

# Build solver with Portuguese
solver = LetterLinkSolver()
if 'Portuguese' in wm.wordlists:
    wordlist = wm.wordlists['Portuguese']['full']
    logger.info(f"Building Trie from Portuguese ({len(wordlist)} words)...")
    count = solver.build_trie_from_list(wordlist)
    logger.info(f"Trie built: {count} words indexed")
else:
    logger.error("Portuguese wordlist not found!")
    exit(1)

# Test grid from the screenshot
# B E S O I
# L N S S F
# E U M T I
# S U E M G
# A N I R P

test_grid = [
    ['B', 'E', 'S', 'O', 'I'],
    ['L', 'N', 'S', 'S', 'F'],
    ['E', 'U', 'M', 'T', 'I'],
    ['S', 'U', 'E', 'M', 'G'],
    ['A', 'N', 'I', 'R', 'P']
]

logger.info(f"Test grid:\n{test_grid}")
logger.info("Solving...")

results = solver.solve_grid(test_grid)
logger.info(f"\nFound {len(results)} words!")

if results:
    logger.info("\nTop 10 words:")
    for i, (word, path, score) in enumerate(results[:10]):
        logger.info(f"  {i+1}. {word.upper()} - {score} pts (path: {path})")
else:
    logger.warning("No words found!")
    logger.info(f"Trie root has {len(solver.trie.root.children)} characters")
    logger.info(f"Sample characters in trie: {list(solver.trie.root.children.keys())}")
