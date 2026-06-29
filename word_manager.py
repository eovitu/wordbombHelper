import bisect
import os
import random
import unicodedata
import threading
import logging

logger = logging.getLogger(__name__)

class WordManager:
    def __init__(self, wordlist_dir='wordlists'):
        self._lock = threading.RLock()
        # Use absolute path relative to this file to ensure wordlists are found regardless of CWD
        base_dir = os.path.dirname(os.path.abspath(__file__))
        if wordlist_dir == 'wordlists':
            self.wordlist_dir = os.path.join(base_dir, 'wordlists')
        else:
            self.wordlist_dir = wordlist_dir
            
        self.wordlists = {}
        self.sublists = {}
        self.used_words = set()
        self.recover_target = 2
        self.recover_exclude = set()
        self.letter_targets = self._build_initial_targets()
        self.current_language = 'Inglês'
        self.current_alpha_char = 'a'
        # Cache for resolved language names to avoid repeated normalization
        self._lang_cache = {}
        # Índices de casamento conservador para o Pipeline B (lazy, por idioma).
        # Objetivo: ZERO falso positivo — só marcamos uma palavra jogada quando a leitura
        # do OCR mapeia para UMA única entrada do dicionário sem ambiguidade. Ver
        # resolve_played_ocr. Construídos fora do lock (não bloqueiam o Pipeline A).
        self._match_index = {}   # lang -> {clean: real_lower}  (chaves acento-insensíveis)
        self._match_ambig = {}   # lang -> set(clean com >1 forma real → ambíguo)
        self._match_by_len = {}  # lang -> {comprimento: [clean...]}  (busca Hamming-1)
        self._match_sorted = {}  # lang -> [clean...] ordenado  (checagem de superset/prefixo)

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

    @staticmethod
    def _normalize_language_name(name: str) -> str:
        """Normalizes language names for accent/case-insensitive matching."""
        if not name:
            return ''
        normalized = unicodedata.normalize('NFD', str(name).strip().lower())
        return ''.join(c for c in normalized if unicodedata.category(c) != 'Mn')

    def _resolve_language_name(self, lang: str) -> str:
        """Resolves configured language name to an available wordlist key."""
        if lang in self._lang_cache:
            return self._lang_cache[lang]

        if lang in self.wordlists:
            self._lang_cache[lang] = lang
            return lang

        normalized_lang = self._normalize_language_name(lang)
        if not normalized_lang:
            return lang

        normalized_map = {
            self._normalize_language_name(key): key
            for key in self.wordlists.keys()
        }

        if normalized_lang in normalized_map:
            return normalized_map[normalized_lang]

        aliases = {
            'portuguese': 'portugues',
        }
        alias_target = aliases.get(normalized_lang)
        if alias_target and alias_target in normalized_map:
            res = normalized_map[alias_target]
            self._lang_cache[lang] = res
            return res

        self._lang_cache[lang] = lang
        return lang

    def set_recover_config(self, target, exclude_str):
        exclude_chars = self._parse_letter_set(exclude_str)
        # If config changed, reset the targets to prevent logic bugs
        if target != self.recover_target or exclude_chars != self.recover_exclude:
            self.recover_target = target
            self.recover_exclude = exclude_chars
            self.letter_targets = self._build_initial_targets()

    def _load_language(self, lang):
        """Loads wordlists for a specific language from the specified directory.
        
        Files named 'Language.txt' are main wordlists.
        Files named 'Language_subname.txt' are sub-lists of 'Language'.
        Acquires lock internally.
        """
        with self._lock:
            self._load_language_unsafe(lang)

    def _load_language_unsafe(self, lang):
        """Internal: Assumes lock is already held. Loads wordlists for a language."""
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
                        
                        # Build length index for faster filtering
                        len_map = {}
                        for i, w_low in enumerate(words_lower):
                            l = len(w_low)
                            if l not in len_map:
                                len_map[l] = []
                            len_map[l].append(i)
                            
                        data = {'full': words, 'lower': words_lower, 'len_map': len_map}

                    if '_' in name:
                        # Sub-list: e.g. 'Portuguese_palindromos' -> lang='Portuguese', sub='palindromos'
                        parts = name.split('_', 1)
                        file_lang, sub = parts[0], parts[1]
                        if file_lang == lang:
                            if lang not in self.sublists:
                                self.sublists[lang] = {}
                            self.sublists[lang][sub] = data
                    else:
                        if name == lang:
                            self.wordlists[name] = data
                except Exception as e:
                    logger.error("Error loading %s: %s", filename, e)

    def get_sublists(self, lang):
        """Returns available sub-list names for the given language."""
        with self._lock:
            resolved_lang = self._resolve_language_name(lang)
            if resolved_lang not in self.sublists:
                self._load_language(resolved_lang)
            return list(self.sublists.get(resolved_lang, {}).keys())

    def get_word(self, prompt, lang='en', min_len=1, max_len=46, strategy='random', priority_letters='', exclude_letters='', starts_with_letters='', priority_min_len=1, priority_max_len=46, priority_sublist='', prefix='', finish_with_letters='', suffix=''):
        """
        Finds a word containing the prompt string or starting with a prefix.
        
        strategies: 'random', 'shortest', 'longest', 'hyphen', 'alpha', 'recover'
        """
        with self._lock:
            lang = self._resolve_language_name(lang)
            if lang not in self.wordlists:
                self._load_language_unsafe(lang)
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

            # Optimize search using pre-lowercased list and length index
            data = self.wordlists[lang]
            len_map = data.get('len_map', {})
        
            candidates = []
            prefix_lower = prefix.lower() if prefix else ''
            suffix_lower = suffix.lower() if suffix else ''
        
            # If length filters are active, only iterate through matching lengths
            target_indices = []
            if has_len_filter:
                for length in range(min_len, max_len + 1):
                    if length in len_map:
                        target_indices.extend(len_map[length])
            else:
                # Fallback to full list if no length filter (rare in practice)
                target_indices = range(len(data['lower']))

            if prefix_lower or suffix_lower:
                for i in target_indices:
                    word_lower = data['lower'][i]
                    if ((not prefix_lower or word_lower.startswith(prefix_lower)) and 
                        (not suffix_lower or word_lower.endswith(suffix_lower)) and 
                        word_lower not in self.used_words):
                        candidates.append(data['full'][i])
            else:
                for i in target_indices:
                    word_lower = data['lower'][i]
                    if prompt in word_lower and word_lower not in self.used_words:
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
                self._mark_used_locked(word)

    def _mark_used_locked(self, word):
        """Marca a palavra como usada. ASSUME que self._lock já está retido."""
        w_lower = word.lower()
        self.used_words.add(w_lower)

        # Clean accents to proper check against 'a'-'z' targets
        w_clean = ''.join(c for c in unicodedata.normalize('NFD', w_lower) if unicodedata.category(c) != 'Mn')

        # Decrease targets for unique letters found in the word
        for char in set(w_clean):
            if char in self.letter_targets and self.letter_targets[char] > 0:
                self.letter_targets[char] -= 1

        # If all targets reached 0, reset the cycle back to the target count
        if all(v == 0 for v in self.letter_targets.values()):
            self.letter_targets = self._build_initial_targets()

    @staticmethod
    def normalize_token(text):
        """Minúsculas + sem acento, preservando hífen e apóstrofe (ex: 'PÁU-D'ALHO' -> "pau-d'alho").

        Chave canônica usada para casar leituras de OCR (Pipeline B) com a wordlist."""
        s = (text or "").strip().lower()
        s = ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')
        return ''.join(ch for ch in s if ch.isalpha() or ch in "-'")

    def _get_match_indexes(self, lang):
        """Constrói (lazy) os índices de casamento do idioma e retorna a chave resolvida.

        O build O(n) roda FORA do lock (a wordlist não muda após carregada), então o
        get_word do Pipeline A nunca espera por ele. Retorna None se o idioma não carregar."""
        with self._lock:
            resolved = self._resolve_language_name(lang)
            if resolved in self._match_index:
                return resolved
            if resolved not in self.wordlists:
                self._load_language_unsafe(resolved)
            data = self.wordlists.get(resolved)
            words_ref = data['lower'] if data else None
        if words_ref is None:
            return None
        idx, ambig = {}, set()
        for real in words_ref:
            c = self.normalize_token(real)
            if not c:
                continue
            cur = idx.get(c)
            if cur is None:
                idx[c] = real
            elif cur != real:
                ambig.add(c)  # mesma forma limpa, palavras reais diferentes → ambíguo
        by_len = {}
        for c in idx:
            by_len.setdefault(len(c), []).append(c)
        sorted_keys = sorted(idx.keys())
        with self._lock:
            if resolved not in self._match_index:
                self._match_index[resolved] = idx
                self._match_ambig[resolved] = ambig
                self._match_by_len[resolved] = by_len
                self._match_sorted[resolved] = sorted_keys
        return resolved

    @staticmethod
    def _has_proper_superset(key, sorted_keys):
        """True se existe palavra mais longa no dicionário que tem `key` como prefixo
        (ex.: 'snowboard' → 'snowboards'). OCR pode ter cortado o fim → ambíguo."""
        i = bisect.bisect_right(sorted_keys, key)
        return i < len(sorted_keys) and sorted_keys[i].startswith(key)

    @staticmethod
    def _unique_hamming1(key, same_len_keys):
        """Retorna a única chave do dicionário a Hamming-1 de `key` (mesmo tamanho),
        ou None se houver zero ou múltiplas (ambíguo). Early-exit ao achar a 2ª."""
        found = None
        for c in same_len_keys:
            diff = 0
            for a, b in zip(key, c):
                if a != b:
                    diff += 1
                    if diff > 1:
                        break
            if diff == 1:
                if found is not None:
                    return None  # múltiplos candidatos → ambíguo
                found = c
        return found

    def resolve_played_ocr(self, ocr_word, lang):
        """Casa a leitura OCR de uma palavra jogada com a forma canônica do dicionário, de
        modo CONSERVADOR (prioridade: zero falso positivo). Marca em used_words só quando
        não-ambíguo. Retorna (status, canonical):
          'marked'    → casou sem ambiguidade e foi marcada (canonical = palavra real);
          'ambiguous' → havia mais de uma interpretação plausível → NÃO marcou;
          'unknown'   → não está no dicionário / sem candidato → NÃO marcou.

        Regras: (1) match exato acento-insensível, aceito só se não houver superset nem
        forma real duplicada; (2) senão, correção por 1 substituição de MESMO tamanho, aceita
        só se houver exatamente um candidato. Inserção/remoção (tamanho diferente) é sempre
        tratada como ambígua."""
        key = self.normalize_token(ocr_word)
        if not key or len(key) < 2:
            return ("unknown", None)
        resolved = self._get_match_indexes(lang)
        if resolved is None:
            return ("unknown", None)
        idx = self._match_index[resolved]
        ambig = self._match_ambig[resolved]

        # (1) Match exato acento-insensível
        if key in idx:
            if key in ambig or self._has_proper_superset(key, self._match_sorted[resolved]):
                return ("ambiguous", None)
            return (self._commit_match(idx[key]), idx[key])

        # (2) Correção por 1 substituição de mesmo tamanho (único candidato)
        cand = self._unique_hamming1(key, self._match_by_len[resolved].get(len(key), ()))
        if cand is not None and cand not in ambig:
            return (self._commit_match(idx[cand]), idx[cand])

        # Múltiplos candidatos OU nenhum candidato de mesmo tamanho.
        # Distinguimos "ambíguo" (havia >1) de "unknown" só para o log de manutenção:
        # _unique_hamming1 já devolveu None para ambos; refazemos um teste barato de existência.
        if self._any_hamming1(key, self._match_by_len[resolved].get(len(key), ())):
            return ("ambiguous", None)
        return ("unknown", None)

    @staticmethod
    def _any_hamming1(key, same_len_keys):
        for c in same_len_keys:
            diff = 0
            for a, b in zip(key, c):
                if a != b:
                    diff += 1
                    if diff > 1:
                        break
            if diff == 1:
                return True
        return False

    def _commit_match(self, real):
        """Marca a forma real como usada (idempotente). Retorna sempre 'marked'."""
        with self._lock:
            if real not in self.used_words:
                self._mark_used_locked(real)
        return "marked"

    def reset_used(self):
        """Resets used words history and clears memory cache of wordlists to force a disk reload."""
        with self._lock:
            self.used_words.clear()
            self.wordlists.clear()
            self.sublists.clear()
            self._match_index.clear()
            self._match_ambig.clear()
            self._match_by_len.clear()
            self._match_sorted.clear()
            self._lang_cache.clear()
            self.letter_targets = self._build_initial_targets()
            self.current_alpha_char = 'a'

    def get_languages(self):
        """Returns all available languages by discovering .txt files in wordlists directory.
        
        Discovers language files (Language.txt, not Language_subname.txt).
        Also loads them for quick access.
        """
        with self._lock:
            if not os.path.exists(self.wordlist_dir):
                logger.warning(f"Wordlist directory not found: {self.wordlist_dir}")
                return []
            
            discovered_langs = set()
            
            # Discover all languages by checking .txt files
            for filename in os.listdir(self.wordlist_dir):
                if filename.endswith('.txt'):
                    # Fix for potential encoding/normalization issues with filenames
                    name = filename[:-4]
                    
                    # Only main lists, not sublists (those have underscore)
                    if '_' not in name:
                        discovered_langs.add(name)
                        # Ensure it's loaded
                        if name not in self.wordlists:
                            try:
                                self._load_language_unsafe(name)
                            except Exception as e:
                                logger.error(f"Failed to load discovered language {name}: {e}")
            
            return sorted(list(discovered_langs))

    def get_sublists_map(self):
        """Returns a map of language -> list of sub-list names."""
        return {lang: list(subs.keys()) for lang, subs in self.sublists.items()}
