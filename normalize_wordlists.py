import os
import unicodedata

def normalize_text(text):
    # Convert to lowercase
    text = text.lower()
    # Remove accents and normalize characters like ç to c
    text = unicodedata.normalize('NFKD', text).encode('ASCII', 'ignore').decode('utf-8')
    return text

def main():
    wordlists_dir = 'wordlists'
    for filename in os.listdir(wordlists_dir):
        if filename.endswith('.txt'):
            filepath = os.path.join(wordlists_dir, filename)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                normalized_content = normalize_text(content)
                
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(normalized_content)
                print(f"Normalized: {filename}")
            except Exception as e:
                print(f"Error processing {filename}: {e}")

if __name__ == '__main__':
    main()
