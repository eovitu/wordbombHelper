
words = [
    'pitia', 'pitias', 'pitica', 'piticas', 'pitico',
    'enrabicha', 'enrabichada', 'enrabichadas', 'enrabichado', 'enrabichados',
    'arlesiana', 'arlesianas', 'arlesiano', 'arlesianos', 'burles',
    'aldraboes', 'baboes', 'boboes', 'bulboesponjosa', 'bulboesponjosas'
]

filepath = r'c:\Users\vitu\Documents\wordbomb\wordlists\Português.txt'

with open(filepath, 'a', encoding='utf-8') as f:
    for word in words:
        f.write(f"\n{word}")

print(f"Added {len(words)} words.")
