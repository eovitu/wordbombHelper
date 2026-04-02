
import os
import unicodedata
import re

def remove_accents(input_str):
    if not input_str: return ""
    nfkd_form = unicodedata.normalize('NFKD', input_str)
    result = "".join([c for c in nfkd_form if not unicodedata.combining(c)])
    result = result.replace('ç', 'c').replace('Ç', 'C')
    # Keep only letters, hyphens, and apostrophes
    result = re.sub(r'[^a-zA-Z\-\']', '', result)
    return result

def is_palindrome(word):
    # Only letters for check
    clean = re.sub(r'[^a-zA-Z]', '', word).lower()
    if len(clean) < 3: return False # Ignore very short ones like 'aa' if not helpful
    return clean == clean[::-1]

STRICT_SUFFIXES = ['ense', 'iense', 'anhense', 'alense', 'onense', 'uense', 'oniano', 'niano', 'politano', 'ico']
GENTILE_HINT_PARTS = {
    'rio', 'grande', 'sul', 'norte', 'leste', 'oeste', 'centro', 'mato', 'grosso', 
    'minas', 'gerais', 'espirito', 'santo', 'santa', 'catarina', 'bahia', 'para', 
    'amapa', 'acre', 'sergipe', 'alagoas', 'maranhao', 'piaui', 'ceara', 'goias', 
    'tocantins', 'rondonia', 'roraima', 'amazonas', 'parana', 'paulista', 'mineiro',
    'fluminense', 'carioca', 'brasil', 'portugal', 'angola', 'mocambique', 'guine',
    'franco', 'luso', 'ibero', 'nipo', 'sino', 'anglo', 'euro', 'afro', 'indo'
}

KNOWN_GENTILES = {
    'carioca', 'gaucho', 'capixaba', 'potiguar', 'mineiro', 'baiano', 'goiano', 
    'brasileiro', 'portugues', 'espanhol', 'frances', 'alemao', 'ingles', 'italiano',
    'chines', 'japones', 'africano', 'americano', 'latino', 'europeu', 'asiatico',
    'arabe', 'judeu', 'israelense', 'palestino', 'russo', 'grego', 'turco',
    'paulista', 'paulistano', 'fluminense', 'barriga-verde', 'catarinense',
    'amazonense', 'acreano', 'piauiense', 'sergipano', 'alagoano', 'pernambucano',
    'paraibano', 'potiguar', 'maranhense', 'tocantinense', 'matogrossense',
    'sul-matogrossense', 'rio-grandense', 'guineense', 'cabo-verdiano', 'timorense',
    'indio', 'negro', 'branco', 'mulato', 'caboclo', 'mameluco', 'cafuzo', 'bantu', 'zulu', 'ioruba', 'jeje'
}

def is_special(word):
    w = word.lower()
    
    # Palindrome Check
    if is_palindrome(w): return True
    
    # Gentile Heuristic
    if w in KNOWN_GENTILES: return True
    
    # Check suffixes in full word or hyphenated parts
    # If hyphenated, we check components
    parts = w.split('-')
    for p in parts:
        if p in GENTILE_HINT_PARTS: return True
        if p in KNOWN_GENTILES: return True
        for s in STRICT_SUFFIXES:
            if p.endswith(s) and len(p) > 5: return True
            
    # Check single word ends in suffix
    if len(w) > 5:
        for s in STRICT_SUFFIXES:
            if w.endswith(s): return True
            
    return False

portuguese_file = r'c:\Users\vitu\Documents\wordbomb\wordlists\Portuguese.txt'
palindromos_file = r'c:\Users\vitu\Documents\wordbomb\wordlists\Portuguese_palindromos.txt'

with open(portuguese_file, 'r', encoding='utf-8') as f:
    words = [line.strip() for line in f if line.strip()]

processed_main = set()
special_words = set()

for w in words:
    clean = remove_accents(w).lower()
    if not clean: continue
    
    processed_main.add(clean)
    if is_special(clean):
        special_words.add(clean)

# Final sort and write
sorted_main = sorted(list(processed_main))
sorted_special = sorted(list(special_words))

with open(portuguese_file, 'w', encoding='utf-8') as f:
    for word in sorted_main:
        f.write(word + '\n')

with open(palindromos_file, 'w', encoding='utf-8') as f:
    for word in sorted_special:
        f.write(word + '\n')

print(f"Update Finished. Main: {len(sorted_main)}, Special: {len(sorted_special)}")
