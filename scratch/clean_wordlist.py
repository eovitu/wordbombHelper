
words_to_remove = {
    'lek', 'lib', 'lol', 'lov', 'lox', 'lub', 'luc', 'lud', 'lue', 'lum', 'lun', 'luo', 'lur', 'lux', 'lad',
    'mad', 'mid', 'mom', 'mob', 'mum', 'mun', 'mut', 'nut'
}

filepath = r'c:\Users\vitu\Documents\wordbomb\wordlists\Português.txt'

with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = [line for line in lines if line.strip().lower() not in words_to_remove]

with open(filepath, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print(f"Removed {len(lines) - len(new_lines)} words.")
