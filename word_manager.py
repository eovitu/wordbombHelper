import os
import random

class WordManager:
    def __init__(self, wordlist_dir='wordlists'):
        self.wordlist_dir = wordlist_dir
        self.wordlists = {}
        self.used_words = set()
        self.current_language = 'English'
        self.current_alpha_char = 'a'
        self.load_wordlists()

    def load_wordlists(self):
        """Loads wordlists from the specified directory."""
        self.wordlists = {} # Clear existing lists before loading
        if not os.path.exists(self.wordlist_dir):
            os.makedirs(self.wordlist_dir)
            return

        for filename in os.listdir(self.wordlist_dir):
            if filename.endswith('.txt'):
                lang = filename.split('.')[0]
                try:
                    with open(os.path.join(self.wordlist_dir, filename), 'r', encoding='utf-8') as f:
                        # Store both original and lowercased for fast search
                        words = [line.strip() for line in f if line.strip()]
                        words_lower = [w.lower() for w in words]
                        self.wordlists[lang] = {
                            'full': words,
                            'lower': words_lower
                        }
                except Exception as e:
                    print(f"Error loading {filename}: {e}")

    def get_word(self, prompt, lang='en', min_len=1, max_len=46, strategy='random', priority_letters='', exclude_letters=''):
        """
        Finds a word containing the prompt string.
        
        strategies: 'random', 'shortest', 'longest', 'hyphen', 'alpha'
        """
        if lang not in self.wordlists:
            return None

        prompt = prompt.lower()
        
        # Optimize search using pre-lowercased list and list comprehension
        data = self.wordlists[lang]
        
        # Prepare exclude set
        exclude_chars = set(exclude_letters.lower().replace(' ', '').replace(',', ''))
        
        candidates = [
            data['full'][i] 
            for i, word_lower in enumerate(data['lower'])
            if prompt in word_lower 
            and min_len <= len(word_lower) <= max_len
            and word_lower not in self.used_words
            and (not exclude_chars or word_lower[0] not in exclude_chars)
        ]

        if not candidates:
            return None

        # Pre-filter: Priority Letters Filtering
        pri_chars = set(priority_letters.lower().replace(' ', '').replace(',', ''))
        if pri_chars:
            # Score candidates
            scored = []
            for w in candidates:
                w_lower = w.lower()
                score = sum(1 for c in pri_chars if c in w_lower)
                scored.append((score, w))
            
            # Find the top score available
            top_score = max(score for score, w in scored)
            if top_score > 0:
                # Override candidates with only the tied top scorers
                candidates = [w for s, w in scored if s == top_score]

        # Apply strategy
        if strategy == 'shortest':
            candidates.sort(key=len)
            # Pick from the top few to avoid always being the same
            return candidates[0]
        elif strategy == 'longest':
            candidates.sort(key=len, reverse=True)
            return candidates[0]
        elif strategy == 'hyphen':
            hyphenated = [w for w in candidates if '-' in w]
            if hyphenated:
                return random.choice(hyphenated)
            # Fallback to random if no hyphens
            return random.choice(candidates)
        elif strategy == 'alpha':
            # Filter for words starting with current_alpha_char
            alpha_candidates = [w for w in candidates if w.lower().startswith(self.current_alpha_char)]
            
            if alpha_candidates:
                word = random.choice(alpha_candidates)
                # Advance char
                self._advance_alpha_char()
                return word
            else:
                # Fallback to random, do NOT advance char
                return random.choice(candidates)
        else: # random
            return random.choice(candidates)
            
    def _advance_alpha_char(self):
        # Cycle 'a' -> 'z' -> 'a'
        if self.current_alpha_char == 'z':
            self.current_alpha_char = 'a'
        else:
            self.current_alpha_char = chr(ord(self.current_alpha_char) + 1)

    def mark_used(self, word):
        if word:
            self.used_words.add(word.lower())

    def reset_used(self):
        self.used_words.clear()

    def get_languages(self):
        return list(self.wordlists.keys())
