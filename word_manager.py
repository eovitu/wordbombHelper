import os
import random
import unicodedata
import threading
import logging

logger = logging.getLogger(__name__)

class WordManager:
    def __init__(self, wordlist_dir='wordlists'):
        self._lock = threading.RLock()
        self.wordlist_dir = wordlist_dir
        self.wordlists = {}
        self.used_words = set()
        self.recover_target = 2
        self.recover_exclude = set()
        self.letter_targets = self._build_initial_targets()
        self.current_language = 'English'
        self.current_alpha_char = 'a'
        self.load_wordlists()

    def _build_initial_targets(self):
        targets = {}
        for i in range(ord('a'), ord('z')+1):
            c = chr(i)
            if c not in self.recover_exclude:
                targets[c] = self.recover_target
        return targets

    @staticmethod
    def _parse_letter_set(s: str) -> set:
        """Parses a comma/space-separated letter string into a set of lowercase chars."""
        return set(s.lower().replace(' ', '').replace(',', '')) if s else set()

    def set_recover_config(self, target, exclude_str):
        exclude_chars = self._parse_letter_set(exclude_str)
        # If config changed, reset the targets to prevent logic bugs
        if target != self.recover_target or exclude_chars != self.recover_exclude:
            self.recover_target = target
            self.recover_exclude = exclude_chars
            self.letter_targets = self._build_initial_targets()

    def load_wordlists(self):
        """Loads wordlists from the specified directory.
        
        Files named 'Language.txt' are main wordlists.
        Files named 'Language_subname.txt' are sub-lists of 'Language'.
        """
        with self._lock:
            self.wordlists = {} # Clear existing lists before loading
            self.sublists = {}  # { 'Portuguese': { 'palindromos': {full, lower}, ... } }
            if not os.path.exists(self.wordlist_dir):
                os.makedirs(self.wordlist_dir)
                return

            for filename in os.listdir(self.wordlist_dir):
                if filename.endswith('.txt'):
                    name = filename[:-4]  # remove .txt
                    try:
                        with open(os.path.join(self.wordlist_dir, filename), 'r', encoding='utf-8') as f:
                            words = [line.strip() for line in f if line.strip()]
                            words_lower = [w.lower() for w in words]
                            data = {'full': words, 'lower': words_lower}

                        if '_' in name:
                            # Sub-list: e.g. 'Portuguese_palindromos' -> lang='Portuguese', sub='palindromos'
                            parts = name.split('_', 1)
                            lang, sub = parts[0], parts[1]
                            if lang not in self.sublists:
                                self.sublists[lang] = {}
                            self.sublists[lang][sub] = data
                        else:
                            self.wordlists[name] = data
                    except Exception as e:
                        logger.error("Error loading %s: %s", filename, e)

    def get_sublists(self, lang):
        """Returns available sub-list names for the given language."""
        return list(self.sublists.get(lang, {}).keys())

    def get_word(self, prompt, lang='en', min_len=1, max_len=46, strategy='random', priority_letters='', exclude_letters='', starts_with_letters='', priority_min_len=1, priority_max_len=46, priority_sublist='', prefix='', finish_with_letters='', suffix=''):
        """
        Finds a word containing the prompt string or starting with a prefix.
        
        strategies: 'random', 'shortest', 'longest', 'hyphen', 'alpha', 'recover'
        """
        with self._lock:
            if lang not in self.wordlists:
                return None

            prompt = prompt.lower()

        # If a priority sub-list is set, try it first, then fall back to main list
            if priority_sublist and lang in self.sublists and priority_sublist in self.sublists[lang]:
                sub_data = self.sublists[lang][priority_sublist]
                sub_matches = [
                    sub_data['full'][i]
                    for i, word_lower in enumerate(sub_data['lower'])
                    if prompt in word_lower
                    and min_len <= len(word_lower) <= max_len
                    and word_lower not in self.used_words
                ]
                if sub_matches:
                    # Found in sub-list — use it directly (skip all other filters for simplicity)
                    return random.choice(sub_matches)

        # Define filter parameters early to avoid doing it per string
            min_len_valid = min_len > 1
            max_len_valid = max_len < 46
            has_len_filter = min_len_valid or max_len_valid
        
        # Optimize search using pre-lowercased list and single pass
            data = self.wordlists[lang]
        
            candidates = []
            prefix_lower = prefix.lower() if prefix else ''
            suffix_lower = suffix.lower() if suffix else ''
        
            if prefix_lower or suffix_lower:
                for i, word_lower in enumerate(data['lower']):
                    if ((not prefix_lower or word_lower.startswith(prefix_lower)) and 
                        (not suffix_lower or word_lower.endswith(suffix_lower)) and 
                        word_lower not in self.used_words):
                        if not has_len_filter or (min_len <= len(word_lower) <= max_len):
                            candidates.append(data['full'][i])
            else:
                for i, word_lower in enumerate(data['lower']):
                    if prompt in word_lower and word_lower not in self.used_words:
                        if not has_len_filter or (min_len <= len(word_lower) <= max_len):
                            candidates.append(data['full'][i])

            if not candidates:
                return None

        # Prepare exclude set
            exclude_chars = self._parse_letter_set(exclude_letters)

        # Filter out exclude_chars from beginning of words, UNLESS it empties the list
            if exclude_chars:
                filtered = [w for w in candidates if w.lower()[0] not in exclude_chars]
                candidates = filtered if filtered else candidates

        # Pre-filter (Starts With):
            starts_chars = self._parse_letter_set(starts_with_letters)
            if starts_chars:
                starts_filtered = [w for w in candidates if w.lower()[0] in starts_chars]
                if starts_filtered:
                    # Only restrict if there are actually matches for the start letter
                    candidates = starts_filtered

        # Pre-filter (Ends With):
            finish_chars = self._parse_letter_set(finish_with_letters)
            if finish_chars:
                finish_filtered = [w for w in candidates if w.lower()[-1] in finish_chars]
                if finish_filtered:
                    # Only restrict if there are actually matches for the end letter
                    candidates = finish_filtered

        # Pre-filter (Priority Length):
            if priority_min_len > 1 or priority_max_len < 46:
                len_filtered = [w for w in candidates if priority_min_len <= len(w) <= priority_max_len]
                if len_filtered:
                    candidates = len_filtered

        # Pre-filter: Priority Letters Filtering (Contains)
            pri_chars = self._parse_letter_set(priority_letters)
            if pri_chars:
                # Score candidates
                scored = []
                for w in candidates:
                    w_lower = w.lower()
                    score = sum(1 for c in pri_chars if c in w_lower)
                    scored.append((score, w))
                
                # Find the top score available
                top_score = max((score for score, w in scored), default=0)
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
                starts_chars = self._parse_letter_set(starts_with_letters)
                
                # If a Starts With letter is being enforced, just return a random candidate and DO NOT advance
                # so we resume the alphabet right where we left off when the priority is removed.
                if starts_chars:
                    return random.choice(candidates)
                    
                # Skip current character if it is in the excluded list
                if exclude_chars and len(exclude_chars) < 26:
                    while self.current_alpha_char in exclude_chars:
                        self._advance_alpha_char()
                
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
            elif strategy == 'recover':
                scored_candidates = []
                for w in candidates:
                    w_lower = w.lower()
                    w_clean = ''.join(c for c in unicodedata.normalize('NFD', w_lower) if unicodedata.category(c) != 'Mn')
                    unique_word_letters = set(w_clean)
                    
                    # Score correlates to how badly the letters are needed (target remaining)
                    # Only score letters that are actually in our target dictionary!
                    score = sum(self.letter_targets[c] for c in unique_word_letters if c in self.letter_targets)
                    scored_candidates.append((score, w))
                
                if not scored_candidates:
                    return random.choice(candidates)
                
                # Find the maximum score
                best_score = max(score for score, w in scored_candidates)
                
                if best_score > 0:
                    # Filter out ones with the best score and pick randomly among them
                    best_words = [w for s, w in scored_candidates if s == best_score]
                    return random.choice(best_words)
                else:
                    # Fallback to random if no candidate helps
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
            with self._lock:
                w_lower = word.lower()
                self.used_words.add(w_lower)
                
                # Clean accents to proper check against 'a'-'z' targets
                w_clean = ''.join(c for c in unicodedata.normalize('NFD', w_lower) if unicodedata.category(c) != 'Mn')
                
                # Decrease targets for unique letters found in the word
                for char in set(w_clean):
                    if char in self.letter_targets:
                        if self.letter_targets[char] > 0:
                            self.letter_targets[char] -= 1
                
                # If all targets reached 0, reset the cycle back to the target count
                if all(v == 0 for v in self.letter_targets.values()):
                    self.letter_targets = self._build_initial_targets()

    def reset_used(self):
        with self._lock:
            self.used_words.clear()
            self.letter_targets = self._build_initial_targets()
            self.current_alpha_char = 'a'

    def get_languages(self):
        return list(self.wordlists.keys())

    def get_sublists_map(self):
        """Returns a map of language -> list of sub-list names."""
        return {lang: list(subs.keys()) for lang, subs in self.sublists.items()}
