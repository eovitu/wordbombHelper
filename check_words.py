"""
Detecta palavras provavelmente erradas na lista de Portuguese.txt.

Critérios usados (conservadores — só flagga erros claros):
1. Sequências de consoantes impossíveis em português
2. Padrão de conjugações de verbos inventados (raiz+sufixos em série)
3. Repetição de letras impossível em português
"""

import re
from collections import defaultdict

with open(r'wordlists\Portuguese.txt', 'r', encoding='utf-8') as f:
    words = [line.strip() for line in f if line.strip()]

word_set_lower = set(w.lower() for w in words)

# ---------- HEURÍSTICA 1: Sequências de consoantes impossíveis ----------
# Sequências que simplesmente não ocorrem em português nativo
IMPOSSIBLE_SEQUENCES = [
    r'[^aeiouáàãâéèêíìîóòõôúùûç][^aeiouáàãâéèêíìîóòõôúùûç][^aeiouáàãâéèêíìîóòõôúùûç][^aeiouáàãâéèêíìîóòõôúùûç]',  # 4+ consoantes seguidas
]

def has_impossible_consonant_cluster(w):
    wl = w.lower()
    for pat in IMPOSSIBLE_SEQUENCES:
        if re.search(pat, wl):
            return True
    return False

# ---------- HEURÍSTICA 2: Padrão de conjugações de verbos fantasmas ----------
# Sufixos típicos de verbos -IR (escapir, etc.)
IR_SUFFIXES = sorted([
    'ir','iu','ia','ias','iam','iamos','imos','is',
    'ira','iras','iram','irao','irei','irem','iremos','ires','irdes','irmos',
    'iria','irias','iriam','iriamos',
    'isse','isses','issem','issemos',
    'iste','istes'
], key=len, reverse=True)

# Sufixos típicos de verbos -AR com formas duplamente aberrantes (atraa, etc.)
FAKE_AR_SUFFIXES = sorted([
    'aa','aas','aam','aaamos','aava','aavas','aavam','aavamos'
], key=len, reverse=True)

def extract_root(w, suffixes):
    wl = w.lower()
    for suf in suffixes:
        if wl.endswith(suf) and len(wl) > len(suf) + 2:
            return wl[:-len(suf)]
    return None

# Group words by their potential "ghost verb" root
ir_roots = defaultdict(list)
ar_fake_roots = defaultdict(list)

for w in words:
    root = extract_root(w, IR_SUFFIXES)
    if root and len(root) >= 3:
        ir_roots[root].append(w)
    
    root2 = extract_root(w, FAKE_AR_SUFFIXES)
    if root2 and len(root2) >= 3:
        ar_fake_roots[root2].append(w)

# Flag roots with 4+ conjugation forms AND whose "infinitive" (root+ir) 
# does NOT appear as a standalone word in the list (i.e., it was never a real verb)
suspicious_groups = {}

for root, group in ir_roots.items():
    if len(group) >= 4:
        infinitive = root + 'ir'
        # Extra check: if the verb root itself is suspicious 
        # (e.g., "escap" from "escapir" — "escap" is not a known Portuguese root for -ir)
        # We flag it if the infinitive doesn't appear in a real-looking way
        if infinitive not in word_set_lower:
            suspicious_groups[f'[VERBO-IR FANTASMA: {infinitive}]'] = group

for root, group in ar_fake_roots.items():
    if len(group) >= 2:
        suspicious_groups[f'[FORMA-AR INVALIDA: {root}...]'] = group

# ---------- HEURÍSTICA 3: Palavras com double-letter impossível ----------
# Ex: "rr" no início, "ll" no início, etc.
def has_impossible_double(w):
    wl = w.lower()
    if re.match(r'^(rr|lh|nh|ch|ss)', wl):
        return True
    # Triple same letter
    if re.search(r'(.)\1\1', wl):
        return True
    return False

impossible_doubles = [w for w in words if has_impossible_double(w.lower())]

# ---------- RESULTADO ----------
output_lines = []

output_lines.append('=' * 70)
output_lines.append('RELATÓRIO DE PALAVRAS SUSPEITAS — Portuguese.txt')
output_lines.append('=' * 70)
output_lines.append('')

output_lines.append('--- GRUPOS DE CONJUGAÇÕES DE VERBOS INEXISTENTES ---')
output_lines.append('(grupos com 4+ formas de um verbo que provavelmente não existe)')
output_lines.append('')

for label, group in sorted(suspicious_groups.items()):
    output_lines.append(f'{label}')
    for w in sorted(group, key=lambda x: x.lower()):
        output_lines.append(f'    {w}')
    output_lines.append('')

output_lines.append('--- PALAVRAS COM PADRÃO DE DUPLA LETRA IMPOSSÍVEL ---')
output_lines.append('')
for w in sorted(impossible_doubles, key=lambda x: x.lower()):
    output_lines.append(f'    {w}')

output_lines.append('')
output_lines.append('--- PALAVRAS COM 4+ CONSOANTES SEGUIDAS ---')
output_lines.append('(pode incluir estrangeirismos válidos — verifique)')
output_lines.append('')

hard_consonants = [w for w in words if has_impossible_consonant_cluster(w.lower())]
for w in sorted(hard_consonants, key=lambda x: x.lower()):
    output_lines.append(f'    {w}')

report = '\n'.join(output_lines)
with open('suspicious_words.txt', 'w', encoding='utf-8') as out:
    out.write(report)

print(report[:3000])
print(f'\n... Salvo em suspicious_words.txt ({len(output_lines)} linhas)')
