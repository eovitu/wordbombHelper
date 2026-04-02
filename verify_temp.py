import sys
import os
sys.path.append(os.getcwd())

from word_manager import WordManager
from typer import Typer
import unicodedata

def test_word_manager_prefix():
    print("Testing WordManager Prefix...")
    wm = WordManager()
    # Test with a known prefix from Portuguese.txt
    # e.g. "ab-r" matches "ab-reacao"
    word = wm.get_word('', lang='Portuguese', prefix='ab-r', strategy='random')
    print(f"Prefix 'ab-r' matched: {word}")
    if word and word.lower().startswith('ab-r'):
        print("✅ SUCCESS: WordManager prefix filter works.")
    else:
        print("❌ FAILURE: WordManager prefix filter failed.")

    # Test case sensitivity/normalization
    # prefix 'ABA' matches 'abacates'
    word = wm.get_word('', lang='Portuguese', prefix='ABA', strategy='random')
    print(f"Prefix 'ABA' matched: {word}")
    if word and word.lower().startswith('aba'):
        print("✅ SUCCESS: Case-insensitive prefix works.")
    else:
        print("❌ FAILURE: Case-insensitive prefix failed.")

if __name__ == "__main__":
    try:
        test_word_manager_prefix()
    except Exception as e:
        print(f"Error: {e}")
