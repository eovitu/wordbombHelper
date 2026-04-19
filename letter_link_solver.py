import unicodedata

class TrieNode:
    def __init__(self):
        self.children = {}
        self.is_word = False
        self.word = None

class Trie:
    def __init__(self):
        self.root = TrieNode()

    def insert(self, word):
        node = self.root
        for char in word:
            if char not in node.children:
                node.children[char] = TrieNode()
            node = node.children[char]
        node.is_word = True
        node.word = word

    def search_prefix(self, prefix):
        node = self.root
        for char in prefix:
            if char not in node.children:
                return None
            node = node.children[char]
        return node

class LetterLinkSolver:
    # Pontuação baseada no padrão do jogo e no print (V=3, G=3, M=2, T=2, S=1, etc)
    LETTER_POINTS = {
        'a': 1, 'b': 2, 'c': 1, 'd': 1, 'e': 1, 'f': 3, 'g': 3, 'h': 3, 
        'i': 1, 'j': 5, 'k': 5, 'l': 1, 'm': 2, 'n': 1, 'o': 1, 'p': 2, 
        'q': 5, 'r': 1, 's': 1, 't': 2, 'u': 1, 'v': 3, 'w': 3, 'x': 5, 
        'y': 3, 'z': 5, 'ç': 1
    }

    def __init__(self):
        self.trie = Trie()
        self.directions = [
            (-1, -1), (-1, 0), (-1, 1),
            (0, -1),           (0, 1),
            (1, -1),  (1, 0),  (1, 1)
        ]
        
    def calculate_score(self, word):
        """Calcula a pontuação da palavra:
        - Base: soma dos pontos de cada letra
        - Multiplicador: SÓ para palavras com 9+ letras
        """
        base_score = sum(self.LETTER_POINTS.get(char, 1) for char in word)
        
        # Multiplicador APENAS para palavras muito longas (9+)
        # 5-8 letras: × 1.0 (sem multiplicador)
        # 9+ letras: × 1.8125
        multiplier = 1.0
        if len(word) >= 9:
            multiplier = 1.8125
        
        total_score = int(round(base_score * multiplier))
        return total_score

    def build_trie_from_list(self, word_list):
        # We re-instantiate to clear memory and start fresh
        self.trie = Trie()
        count = 0
        for word in word_list:
            # Keep original to detect unsupported separators (apostrophe, hyphen, spaces)
            original_word = word.lower().strip()

            # Letter Link grid only has letters; skip words with separators instead of collapsing them
            # Example: o'odham must NOT become oodham.
            if any(not (ch.isalpha() or unicodedata.category(ch) == 'Mn') for ch in unicodedata.normalize('NFD', original_word)):
                continue

            # Clean and normalize (ç -> c, etc) for the grid solver
            clean_word = original_word
            # Normalize accents
            clean_word = "".join(
                c for c in unicodedata.normalize('NFD', clean_word)
                if unicodedata.category(c) != 'Mn'
            )
            # Keep only pure alphabetical entries
            if not clean_word.isalpha():
                continue
            
            # Only add words with min length 2
            if len(clean_word) >= 2:
                self.trie.insert(clean_word)
                count += 1
        return count

    def _dfs(self, r, c, node, grid, visited, current_path, all_found):
        # Out of bounds
        if r < 0 or r >= len(grid) or c < 0 or c >= len(grid[0]):
            return
        
        # Already visited in this path
        if visited[r][c]:
            return
            
        char = grid[r][c].lower()
        if not char.isalpha():
            return
            
        # No such prefix
        if char not in node.children:
            return
            
        next_node = node.children[char]
        
        # Mark visited and append to path
        visited[r][c] = True
        current_path.append((r, c))
        
        if next_node.is_word:
            word = next_node.word
            # Keep the path coordinates
            path_coords = list(current_path)
            # If we already found this word, we can skip or keep the shortest path?
            # Actually, keeping the first path is usually fine.
            if word not in all_found or len(path_coords) > len(all_found[word]):
                all_found[word] = path_coords

        # Explore 8 directions
        for dr, dc in self.directions:
            self._dfs(r + dr, c + dc, next_node, grid, visited, current_path, all_found)
            
        # Backtrack
        visited[r][c] = False
        current_path.pop()

    def solve_grid(self, grid_matrix):
        """
        grid_matrix: list of lists (5x5) containing single characters
        Returns: A dictionary of { "word": [(r1,c1), (r2,c2), ...] }
        """
        if not grid_matrix or not grid_matrix[0]:
            return {}
            
        rows = len(grid_matrix)
        cols = len(grid_matrix[0])
        
        all_found = {} # word -> path coordinates
        visited = [[False for _ in range(cols)] for _ in range(rows)]
        
        for r in range(rows):
            for c in range(cols):
                self._dfs(r, c, self.trie.root, grid_matrix, visited, [], all_found)
                
        # Build final list with scores: (word, path, score)
        results_with_score = []
        for word, path in all_found.items():
            score = self.calculate_score(word)
            results_with_score.append((word, path, score))
            
        # Sort by best score first (break ties with length)
        sorted_results = sorted(results_with_score, key=lambda x: (x[2], len(x[0])), reverse=True)
        return sorted_results
