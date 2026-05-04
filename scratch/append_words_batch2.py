
words = [
    'coercibilidade', 'coercibilidades', 'cognoscibilidade', 'cognoscibilidades', 'imiscibilidade',
    'boavisteira', 'boavisteiras', 'boavisteiro', 'boavisteiros', 'desensaboava',
    'amnio', 'amniocentese', 'amniocenteses', 'amniocoriais', 'amniocorial',
    'antilusitana', 'antilusitanas', 'antilusitanismo', 'antilusitanismos', 'antilusitano',
    'tresnoita', 'tresnoitada', 'tresnoitadas', 'tresnoitado', 'tresnoitados'
]

filepath = r'c:\Users\vitu\Documents\wordbomb\wordlists\Português.txt'

with open(filepath, 'a', encoding='utf-8') as f:
    for word in words:
        f.write(f"\n{word}")

print(f"Added {len(words)} words.")
