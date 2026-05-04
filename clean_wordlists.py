#!/usr/bin/env python3
"""Remove words with invalid characters from wordlists."""

import re
from pathlib import Path

# Characters to remove words containing
INVALID_CHARS = {',', '.', '-', '=', "'", '"'}
# Also remove words with numbers
INVALID_PATTERN = re.compile(r'[,.\-=\'\"\d]')

def clean_wordlist(file_path):
    """Remove invalid words from a wordlist file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # Filter out invalid words
        cleaned_lines = []
        removed_count = 0
        
        for line in lines:
            word = line.strip()
            
            # Skip empty lines
            if not word:
                cleaned_lines.append(line)
                continue
            
            # Check if word contains invalid characters
            if INVALID_PATTERN.search(word):
                removed_count += 1
                print(f"  Removido: {word}")
            else:
                cleaned_lines.append(line)
        
        # Write back to file
        with open(file_path, 'w', encoding='utf-8') as f:
            f.writelines(cleaned_lines)
        
        return removed_count
    
    except Exception as e:
        print(f"Erro ao processar {file_path}: {e}")
        return 0

# Process all wordlist files
wordlist_dir = Path('wordlists')
if wordlist_dir.exists():
    txt_files = sorted(wordlist_dir.glob('*.txt'))
    
    for file_path in txt_files:
        print(f"\nProcessando: {file_path.name}")
        removed = clean_wordlist(file_path)
        print(f"  Total removido: {removed} palavras")
else:
    print("Pasta 'wordlists' não encontrada!")
