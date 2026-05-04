import sys

def process_file(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # Strip whitespace and convert to lowercase
    processed_lines = [line.strip().lower() for line in lines if line.strip()]
    
    # Remove duplicates while preserving order
    unique_lines = list(dict.fromkeys(processed_lines))
    
    # Write back to file
    with open(file_path, 'w', encoding='utf-8') as f:
        for line in unique_lines:
            f.write(line + '\n')

if __name__ == "__main__":
    file_path = r"c:\Users\vitu\Documents\wordbomb\wordlists\Português.txt"
    process_file(file_path)