import sys
import os

# Add root dir to path
sys.path.append(os.getcwd())

from word_manager import WordManager

wm = WordManager()
wm.get_languages() # Trigger discovery and loading

lang = 'Português'
prompt = 'tzc'

# Manual check
words = wm.wordlists.get(lang, {}).get('lower', [])
full_words = wm.wordlists.get(lang, {}).get('full', [])
matches = [full_words[i] for i, w in enumerate(words) if prompt in w]

print(f"Manual search for '{prompt}' in '{lang}':")
print(matches)

# API check
result = wm.get_word(prompt, lang=lang)
print(f"API result for '{prompt}': {result}")

# Check specific word
target = "xoloitzcuintle"
found = any(w == target.lower() for w in words)
print(f"Is '{target}' in list? {found}")

if found:
    idx = words.index(target.lower())
    print(f"Index of '{target}': {idx}")
    print(f"Full word at index: {full_words[idx]}")
    print(f"Prompt '{prompt}' in '{target}'? {prompt in target.lower()}")
