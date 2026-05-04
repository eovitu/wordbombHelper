
words = [
    'ameijoa', 'ameijoada', 'ameijoadas', 'ameijoado', 'ameijoados',
    'quinquagenaria', 'quinquagenarias', 'quinquagenario', 'quinquagenarios', 'quinquagesima'
]

filepath = r'c:\Users\vitu\Documents\wordbomb\wordlists\Português.txt'

with open(filepath, 'a', encoding='utf-8') as f:
    for word in words:
        f.write(f"\n{word}")

print(f"Added {len(words)} words.")
