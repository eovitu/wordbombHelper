import os

def lowercase_wordlists():
    wordlists_dir = 'wordlists'
    if not os.path.exists(wordlists_dir):
        print("Pasta 'wordlists' não encontrada!")
        return

    for filename in os.listdir(wordlists_dir):
        if filename.endswith('.txt'):
            filepath = os.path.join(wordlists_dir, filename)
            print(f"Processando {filename}...")
            
            content = None
            encodings = ['utf-8', 'latin-1', 'cp1252']
            
            used_encoding = 'utf-8'
            for enc in encodings:
                try:
                    with open(filepath, 'r', encoding=enc) as f:
                        content = f.read()
                    used_encoding = enc
                    break
                except UnicodeDecodeError:
                    continue
            
            if content is not None:
                lowered_content = content.lower()
                with open(filepath, 'w', encoding=used_encoding) as f:
                    f.write(lowered_content)
                print(f"Sucesso: {filename} ({used_encoding})")
            else:
                print(f"Erro: Não foi possível ler {filename}")

if __name__ == '__main__':
    lowercase_wordlists()
