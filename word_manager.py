import bisect
import os
import random
import unicodedata
import threading
import logging
import tempfile

logger = logging.getLogger(__name__)

class WordManager:
    def __init__(self, wordlist_dir='wordlists', personal_dictionary=None):
        self._lock = threading.RLock()
        # Use absolute path relative to this file to ensure wordlists are found regardless of CWD
        base_dir = os.path.dirname(os.path.abspath(__file__))
        if wordlist_dir == 'wordlists':
            self.wordlist_dir = os.path.join(base_dir, 'wordlists')
        else:
            self.wordlist_dir = wordlist_dir
        self.personal_dictionary = personal_dictionary
            
        self.wordlists = {}
        self.sublists = {}
        self.used_words = set()
        self._recover_counted_words = set()
        self.rejected_words = set()
        self.confirmed_word_count = 0
        self.recover_mode = 'casual'
        self.recover_cycle = 1
        self.recover_target = 1
        self.recover_exclude = {'k', 'w', 'y'}
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
        # Índice "só-letras" (sem - e '): recupera leituras onde o OCR perdeu/inventou
        # pontuação (ex.: 'paudalho' → "pau-d'alho"). Conservador: alpha que mapeia para
        # mais de uma palavra real é marcado como ambíguo. Ver resolve_played_ocr passo (2).
        self._match_alpha = {}       # lang -> {alpha_only: real_lower}
        self._match_alpha_ambig = {} # lang -> set(alpha_only com >1 forma real → ambíguo)

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
        """Compatibility entry point for callers that still pass a target."""
        exclude_chars = self._parse_letter_set(exclude_str)
        # If config changed, reset the targets to prevent logic bugs
        if target != self.recover_target or exclude_chars != self.recover_exclude:
            self.recover_target = target
            self.recover_exclude = exclude_chars
            self.letter_targets = self._build_initial_targets()

    def configure_recover(self, mode='casual', exclude_str=''):
        if mode not in ('casual', 'ranked'):
            raise ValueError('recover_mode must be casual or ranked')
        excluded = {'k', 'w', 'y'} | self._parse_letter_set(exclude_str)
        with self._lock:
            if mode == self.recover_mode and excluded == self.recover_exclude:
                return
            self.recover_mode = mode
            self.recover_exclude = excluded
            self.recover_cycle = 1
            self.recover_target = self._recover_target_for_cycle()
            self.letter_targets = self._build_initial_targets()

    def _recover_target_for_cycle(self):
        if self.recover_mode == 'ranked':
            return min(5, self.recover_cycle + 2)
        return 1 if self.recover_cycle == 1 else 2

    def recover_progress(self):
        with self._lock:
            return {
                'mode': self.recover_mode,
                'cycle': self.recover_cycle,
                'target': self.recover_target,
                'confirmed_words': self.confirmed_word_count,
                'preferred_max_length': self._recover_preferred_max_length(),
                'fast_strategic': self.confirmed_word_count >= 150,
                'remaining': dict(self.letter_targets),
            }

    def _recover_preferred_max_length(self):
        """Soft length target that follows the match's increasing speed."""
        played = self.confirmed_word_count
        if played < 25:
            return None
        if played < 40:
            return 40
        if played < 50:
            return 35
        if played < 70:
            return 25
        if played < 100:
            return 20
        return 15

    def _load_language(self, lang):
        """Loads wordlists for a specific language from the specified directory.
        
        Files named 'Language.txt' are main wordlists.
        Files named 'Language_subname.txt' are sub-lists of 'Language'.
        Acquires lock internally.
        """
        with self._lock:
            self._load_language_unsafe(lang)

    def _load_language_unsafe(self, lang):
        """Internal: Assumes lock is already held. Loads wordlists for a language.

        Só abre os arquivos cujo nome casa com `lang` (lista principal ou sublista).
        Antes este loop abria e parseava TODOS os .txt da pasta (inclusive os 3MB de
        outro idioma) para carregar um só — O(arquivos) de IO desperdiçado por chamada.
        """
        if not os.path.exists(self.wordlist_dir):
            os.makedirs(self.wordlist_dir)
            return

        for filename in os.listdir(self.wordlist_dir):
            if not filename.endswith('.txt'):
                continue
            name = filename[:-4]  # remove .txt
            if '_' in name:
                # Sub-list: e.g. 'Portuguese_palindromos' -> lang='Portuguese', sub='palindromos'
                file_lang, sub = name.split('_', 1)
            else:
                file_lang, sub = name, None
            if file_lang != lang:
                continue  # arquivo de outro idioma — não abre/parseia

            try:
                with open(os.path.join(self.wordlist_dir, filename), 'r', encoding='utf-8') as f:
                    words = [line.strip() for line in f if line.strip()]
                words_lower = [w.lower() for w in words]

                # Build length index for faster filtering
                len_map = {}
                for i, w_low in enumerate(words_lower):
                    len_map.setdefault(len(w_low), []).append(i)

                data = {'full': words, 'lower': words_lower, 'len_map': len_map}

                if sub is not None:
                    if lang not in self.sublists:
                        self.sublists[lang] = {}
                    self.sublists[lang][sub] = data
                else:
                    self.wordlists[name] = data
            except Exception as e:
                logger.error("Error loading %s: %s", filename, e)

        if self.personal_dictionary is not None:
            personal = self.personal_dictionary.get_words(lang)
            if personal:
                data = self.wordlists.get(lang, {'full': [], 'lower': [], 'len_map': {}})
                seen = set(data['lower'])
                for word in personal:
                    lower = word.lower()
                    if lower in seen:
                        continue
                    index = len(data['full'])
                    data['full'].append(word)
                    data['lower'].append(lower)
                    data['len_map'].setdefault(len(lower), []).append(index)
                    seen.add(lower)
                self.wordlists[lang] = data

    def refresh_language(self, lang):
        """Reload one language after personal edits without clearing match history."""
        with self._lock:
            resolved = self._resolve_language_name(lang)
            self.wordlists.pop(resolved, None)
            self.sublists.pop(resolved, None)
            for cache in (self._match_index, self._match_ambig, self._match_by_len,
                          self._match_sorted, self._match_alpha, self._match_alpha_ambig):
                cache.pop(resolved, None)
            self._load_language_unsafe(resolved)

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
            candidates, is_sublist = self._produce_candidates_locked(
                prompt, lang, min_len, max_len, priority_min_len, priority_max_len,
                priority_letters, exclude_letters, starts_with_letters, finish_with_letters,
                priority_sublist, prefix, suffix)
            if not candidates:
                return None
            return self._pick_locked(candidates, is_sublist, strategy,
                                     exclude_letters, starts_with_letters)

    def get_candidates(self, prompt, lang='en', min_len=1, max_len=46, strategy='random', priority_letters='', exclude_letters='', starts_with_letters='', priority_min_len=1, priority_max_len=46, priority_sublist='', prefix='', finish_with_letters='', suffix=''):
        """Lista ORDENADA de candidatos para a sessão de sugestões (feature Reroll).

        Calcula a busca UMA vez (mesmo filtro pesado do get_word) e devolve
        [escolha_primária] + alternativas embaralhadas. O índice 0 é exatamente o que o
        solver escolheria (get_word), então a navegação por índice (R/Shift+R) não refaz
        nenhuma busca. NÃO marca nada como usada."""
        with self._lock:
            candidates, is_sublist = self._produce_candidates_locked(
                prompt, lang, min_len, max_len, priority_min_len, priority_max_len,
                priority_letters, exclude_letters, starts_with_letters, finish_with_letters,
                priority_sublist, prefix, suffix)
            if not candidates:
                return []
            primary = self._pick_locked(candidates, is_sublist, strategy,
                                        exclude_letters, starts_with_letters)
            rest = list(candidates)
            try:
                rest.remove(primary)
            except ValueError:
                pass
            random.shuffle(rest)
            return [primary] + rest

    def _produce_candidates_locked(self, prompt, lang, min_len, max_len, priority_min_len,
                                   priority_max_len, priority_letters, exclude_letters,
                                   starts_with_letters, finish_with_letters, priority_sublist,
                                   prefix, suffix):
        """Filtro pesado compartilhado por get_word e get_candidates. ASSUME lock retido.
        Retorna (candidatos, is_sublist). Lista vazia se nada casar."""
        lang = self._resolve_language_name(lang)
        if lang not in self.wordlists:
            self._load_language_unsafe(lang)
        if lang not in self.wordlists:
            return [], False

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
                and word_lower not in self.rejected_words
            ]
            if sub_matches:
                # Found in sub-list — use it directly (skip all other filters for simplicity)
                return sub_matches, True

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
                    word_lower not in self.used_words and word_lower not in self.rejected_words):
                    candidates.append(data['full'][i])
        else:
            for i in target_indices:
                word_lower = data['lower'][i]
                if (prompt in word_lower and word_lower not in self.used_words
                        and word_lower not in self.rejected_words):
                    candidates.append(data['full'][i])

        if not candidates:
            return [], False

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

        return candidates, False

    def _pick_locked(self, candidates, is_sublist, strategy, exclude_letters, starts_with_letters):
        """Escolhe UMA palavra dentre os candidatos já filtrados. ASSUME lock retido.
        Lógica de estratégia idêntica à versão anterior do get_word."""
        if is_sublist:
            return random.choice(candidates)

        exclude_chars = self._parse_letter_set(exclude_letters)

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

            preferred_max = self._recover_preferred_max_length()
            if preferred_max is not None:
                helpful = [(score, word) for score, word in scored_candidates if score > 0]
                pool = helpful or scored_candidates
                if self.confirmed_word_count >= 150 and helpful:
                    best_efficiency = max(score / len(word) for score, word in helpful)
                    efficient = [
                        (score, word) for score, word in helpful
                        if score / len(word) == best_efficiency
                    ]
                    shortest = min(len(word) for _, word in efficient)
                    return random.choice([
                        word for _, word in efficient if len(word) == shortest
                    ])

                preferred = [(score, word) for score, word in pool if len(word) <= preferred_max]
                if preferred:
                    pool = preferred
                else:
                    shortest_length = min(len(word) for _, word in pool)
                    pool = [(score, word) for score, word in pool if len(word) == shortest_length]

                best_score = max(score for score, _ in pool)
                best_words = [word for score, word in pool if score == best_score]
                shortest_best = min(len(word) for word in best_words)
                return random.choice([word for word in best_words if len(word) == shortest_best])

            # No começo da partida, maximize a cobertura como antes.
            best_score = max(score for score, w in scored_candidates)

            if best_score > 0:
                # Filter out ones with the best score and pick randomly among them
                best_words = [w for s, w in scored_candidates if s == best_score]
                return random.choice(best_words)
            else:
                # Fallback to random if no candidate helps
                return random.choice(candidates)
        else:  # random
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

    def confirm_own_word(self, word):
        """Count an accepted own word even when SOLVE already marked it unavailable."""
        if word:
            with self._lock:
                self.used_words.add(word.lower())
                self._count_recover_locked(word)

    def reject_word(self, word):
        if word:
            with self._lock:
                normalized = word.lower()
                self.rejected_words.add(normalized)
                language = self._resolve_language_name(self.current_language)
                self._remove_word_from_language_files_locked(language, normalized)
                if self.personal_dictionary is not None:
                    personal = self.personal_dictionary.get_words(language)
                    if normalized in personal:
                        self.personal_dictionary.delete(language, normalized)
                self.refresh_language(language)

    def _remove_word_from_language_files_locked(self, language, rejected):
        """Remove permanentemente a palavra da lista principal e sublistas do idioma."""
        if not os.path.isdir(self.wordlist_dir):
            return
        for filename in os.listdir(self.wordlist_dir):
            if not filename.endswith('.txt'):
                continue
            stem = filename[:-4]
            if stem != language and not stem.startswith(language + '_'):
                continue
            path = os.path.join(self.wordlist_dir, filename)
            with open(path, 'r', encoding='utf-8') as handle:
                lines = handle.readlines()
            kept = [line for line in lines if line.strip().lower() != rejected]
            if len(kept) == len(lines):
                continue
            fd, temporary = tempfile.mkstemp(
                prefix=f'.{filename}.', suffix='.tmp', dir=self.wordlist_dir, text=True)
            try:
                with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as handle:
                    for line in kept:
                        handle.write(line.rstrip('\r\n') + '\n')
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temporary, path)
            except Exception:
                try:
                    os.unlink(temporary)
                except FileNotFoundError:
                    pass
                raise

    def mark_unavailable(self, word):
        """Exclude a played word without changing this player's Recover progress."""
        if word:
            with self._lock:
                self.used_words.add(word.lower())

    def _mark_used_locked(self, word):
        """Marca a palavra como usada. ASSUME que self._lock já está retido."""
        w_lower = word.lower()
        if w_lower in self.used_words:
            return
        self.used_words.add(w_lower)
        self._count_recover_locked(word)

    def _count_recover_locked(self, word):
        w_lower = word.lower()
        if w_lower in self._recover_counted_words:
            return
        self._recover_counted_words.add(w_lower)
        self.confirmed_word_count += 1

        # Clean accents to proper check against 'a'-'z' targets
        w_clean = ''.join(c for c in unicodedata.normalize('NFD', w_lower) if unicodedata.category(c) != 'Mn')

        # Decrease targets for unique letters found in the word
        for char in set(w_clean):
            if char in self.letter_targets and self.letter_targets[char] > 0:
                self.letter_targets[char] -= 1

        # If all targets reached 0, reset the cycle back to the target count
        if all(v == 0 for v in self.letter_targets.values()):
            self.recover_cycle += 1
            self.recover_target = self._recover_target_for_cycle()
            self.letter_targets = self._build_initial_targets()

    @staticmethod
    def normalize_token(text):
        """Minúsculas + sem acento, preservando hífen e apóstrofe (ex: 'PÁU-D'ALHO' -> "pau-d'alho").

        Chave canônica usada para casar leituras de OCR (Pipeline B) com a wordlist."""
        s = (text or "").strip().lower()
        s = ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')
        # Canonicaliza variantes de apóstrofe (curvo ’/‘, acento ´, crase `) para o reto ',
        # que é o usado no dicionário — o OCR costuma devolver o curvo ’ (U+2019).
        for ch in "’‘´`":
            s = s.replace(ch, "'")
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
        # Índice só-letras (remove - e '): casa leituras com pontuação divergente.
        # Conservador: se duas palavras reais colapsam para a mesma forma só-letras, ela
        # vira ambígua (não marca). Punct-key já ambíguo propaga para a forma só-letras.
        alpha_idx, alpha_ambig = {}, set()
        for c, real in idx.items():
            a = c.replace('-', '').replace("'", '')
            if len(a) < 2:
                continue
            if c in ambig:
                alpha_ambig.add(a)
                continue
            cur = alpha_idx.get(a)
            if cur is None:
                alpha_idx[a] = real
            elif cur != real:
                alpha_ambig.add(a)
        with self._lock:
            if resolved not in self._match_index:
                self._match_index[resolved] = idx
                self._match_ambig[resolved] = ambig
                self._match_by_len[resolved] = by_len
                self._match_sorted[resolved] = sorted_keys
                self._match_alpha[resolved] = alpha_idx
                self._match_alpha_ambig[resolved] = alpha_ambig
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

    def resolve_played_ocr(self, ocr_word, lang, count_recover=True):
        """Casa a leitura OCR de uma palavra jogada com a forma canônica do dicionário, de
        modo CONSERVADOR (prioridade: zero falso positivo). Marca em used_words só quando
        não-ambíguo. Retorna (status, canonical):
          'marked'    → casou sem ambiguidade e foi marcada (canonical = palavra real);
          'ambiguous' → havia mais de uma interpretação plausível → NÃO marcou;
          'unknown'   → não está no dicionário / sem candidato → NÃO marcou.

        Regras (em ordem): (1) match exato acento-insensível, aceito só se não houver superset
        nem forma real duplicada; (2) recuperação por remoção de pontuação ('-' e "'"), aceita
        só se a forma só-letras mapear para UMA palavra real; (3) correção por 1 substituição
        de MESMO tamanho, aceita só se houver exatamente um candidato. Em todos, ambiguidade
        nunca marca — prioridade é zero falso positivo."""
        key = self.normalize_token(ocr_word)
        if not key or len(key) < 2:
            return ("unknown", None)
        resolved = self._get_match_indexes(lang)
        if resolved is None:
            return ("unknown", None)
        # Snapshot dos índices SOB o lock: reset_used() pode limpá-los em outra thread
        # entre o build e o uso. Pegamos as referências de uma vez para evitar KeyError.
        with self._lock:
            idx = self._match_index.get(resolved)
            ambig = self._match_ambig.get(resolved)
            sorted_keys = self._match_sorted.get(resolved)
            by_len = self._match_by_len.get(resolved)
            alpha_idx = self._match_alpha.get(resolved)
            alpha_ambig = self._match_alpha_ambig.get(resolved)
        if idx is None:
            return ("unknown", None)
        same_len = by_len.get(len(key), ()) if by_len else ()

        # (1) Match exato acento-insensível
        if key in idx:
            if key in ambig or self._has_proper_superset(key, sorted_keys):
                return ("ambiguous", None)
            return (self._commit_match(idx[key], count_recover), idx[key])

        # (2) Recuperação por remoção de pontuação: o OCR pode ter perdido ou inventado um
        # '-' ou "'". Compara a forma só-letras com o índice só-letras. Aceita SÓ se mapear
        # a UMA palavra real (colisão → ambíguo) — mantém o "zero falso positivo".
        if alpha_idx is not None:
            alpha_key = key.replace('-', '').replace("'", '')
            if len(alpha_key) >= 2:
                if alpha_key in alpha_ambig:
                    return ("ambiguous", None)
                real_alpha = alpha_idx.get(alpha_key)
                if real_alpha is not None:
                    return (self._commit_match(real_alpha, count_recover), real_alpha)

        # (3) Correção por 1 substituição de mesmo tamanho (único candidato)
        cand = self._unique_hamming1(key, same_len)
        if cand is not None and cand not in ambig:
            return (self._commit_match(idx[cand], count_recover), idx[cand])

        # Múltiplos candidatos OU nenhum candidato de mesmo tamanho.
        # Distinguimos "ambíguo" (havia >1) de "unknown" só para o log de manutenção:
        # _unique_hamming1 já devolveu None para ambos; refazemos um teste barato de existência.
        if self._any_hamming1(key, same_len):
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

    def _commit_match(self, real, count_recover=True):
        """Marca a forma real como usada (idempotente). Retorna sempre 'marked'."""
        with self._lock:
            if real not in self.used_words:
                if count_recover:
                    self._mark_used_locked(real)
                else:
                    self.used_words.add(real.lower())
        return "marked"

    def reset_used(self):
        """Resets used words history and clears memory cache of wordlists to force a disk reload."""
        with self._lock:
            self.used_words.clear()
            self._recover_counted_words.clear()
            self.rejected_words.clear()
            self.confirmed_word_count = 0
            self.wordlists.clear()
            self.sublists.clear()
            self._match_index.clear()
            self._match_ambig.clear()
            self._match_by_len.clear()
            self._match_sorted.clear()
            self._match_alpha.clear()
            self._match_alpha_ambig.clear()
            self._lang_cache.clear()
            self.recover_cycle = 1
            self.recover_target = self._recover_target_for_cycle()
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
