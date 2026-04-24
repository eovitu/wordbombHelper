"""
Download and process word lists for missing languages.
Sources:
  - Danish  : hermitdave/FrequencyWords (da_50k.txt)
  - Norwegian: hermitdave/FrequencyWords (no_50k.txt)
  - Polish   : hermitdave/FrequencyWords (pl_50k.txt)
  - Russian  : hermitdave/FrequencyWords (ru_50k.txt)

These are frequency-ranked word lists extracted from Wikipedia/OpenSubtitles.
Words are filtered to keep only alphabetic entries with 3+ characters.
"""

import urllib.request
import os
import unicodedata
import re
import sys

BASE_URL = "https://raw.githubusercontent.com/hermitdave/FrequencyWords/master/content/2018"

LANGUAGES = {
    "Dinamarquês": ("da", "da_50k.txt"),
    "Norueguês": ("no", "no_50k.txt"),
    "Polonês":   ("pl", "pl_50k.txt"),
    "Russo":     ("ru", "ru_50k.txt"),
}

WORDLIST_DIR = os.path.join(os.path.dirname(__file__), "wordlists")

def is_valid_word(word: str, lang_code: str) -> bool:
    """Keep only alphabetic words with 3+ characters."""
    if len(word) < 3:
        return False
    # Allow letters from any script (covers Cyrillic for Russian)
    for ch in word:
        cat = unicodedata.category(ch)
        if not cat.startswith("L"):
            return False
    return True

def download_and_process(lang_name: str, lang_code: str, filename: str) -> int:
    url = f"{BASE_URL}/{lang_code}/{filename}"
    out_path = os.path.join(WORDLIST_DIR, f"{lang_name}.txt")

    # Skip if file already has content
    if os.path.exists(out_path) and os.path.getsize(out_path) > 1000:
        print(f"[SKIP] {lang_name}.txt already has content ({os.path.getsize(out_path)} bytes). Delete it to re-download.")
        return 0

    print(f"[DOWNLOADING] Baixando {lang_name} de: {url}")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as response:
            raw = response.read().decode("utf-8", errors="ignore")
    except Exception as e:
        print(f"[ERRO] Falha ao baixar {lang_name}: {e}")
        return 0

    words = []
    seen = set()
    for line in raw.splitlines():
        parts = line.strip().split()
        if not parts:
            continue
        word = parts[0].lower()
        if word not in seen and is_valid_word(word, lang_code):
            seen.add(word)
            words.append(word)

    # Sort alphabetically
    words.sort()

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(words))

    print(f"[OK] {lang_name}.txt -> {len(words)} palavras salvas em {out_path}")
    return len(words)


def main():
    os.makedirs(WORDLIST_DIR, exist_ok=True)
    total = 0
    for lang_name, (lang_code, filename) in LANGUAGES.items():
        count = download_and_process(lang_name, lang_code, filename)
        total += count
    print(f"\nConcluído! Total de palavras adicionadas: {total}")


if __name__ == "__main__":
    main()
