import time
import random
import pyautogui
import threading
import keyboard

# Fail-safe: Move mouse to upper-left corner to abort
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.001 # Minimize default pause between actions

# QWERTY Proximity Map for realistic typos (Narrowed down for ultra-realism)
QWERTY_MAP = {
    'q': 'wa', 'w': 'qse', 'e': 'wsdr', 'r': 'edf', 't': 'rfgy', 'y': 'tghu', 'u': 'yhij', 'i': 'ujko', 'o': 'iklp', 'p': 'ol',
    'a': 'qwsz', 's': 'awedxz', 'd': 'serfcx', 'f': 'drtgvc', 'g': 'ftyhbv', 'h': 'gyujnb', 'j': 'huikmn', 'k': 'jiol,m', 'l': 'kop',
    'z': 'asx', 'x': 'zsdc', 'c': 'xdfv', 'v': 'cfgb', 'b': 'vghn', 'n': 'bhjm', 'm': 'njk,',
    '.': 'm,', ',': 'mn.', ' ': 'cvbnm',
    'á': 'asw', 'ã': 'asw', 'à': 'asw', 'â': 'asw',
    'é': 'erdw', 'ê': 'erdw',
    'í': 'iujk',
    'ó': 'olp', 'õ': 'olp', 'ô': 'olp',
    'ú': 'uyjh',
    'ç': 'l.;'
}

# Letters that are generally harder to reach or less common, causing micro-hesitations
DIFFICULT_LETTERS = set('qwzxkyh')

class Typer:
    def __init__(self):
        self.is_typing = False
        self._abort = False
        # Tecla de atalho global para cancelar a digitação
        keyboard.on_press_key('insert', self._on_insert_pressed)

    def _on_insert_pressed(self, e):
        # A API de hook de teclado funciona no background. Se estivermos digitando, abortamos.
        # Preferimos usar Insert ou Esc, pois o Backspace nós mesmos apertamos pra apagar erros!
        if self.is_typing:
            self._abort = True

    def type_word(self, word, wpm=60, error_rate=0.0, auto_tab=True, hesitation_prob=0.05, retry_rate=0.0, late_error_rate=0.0, max_typos=2, max_late_errors=1, return_tab=False, delayed_type=False, add_period_prob=0.0):
        """
        Types the word simulating human typing.
        
        :param word: The word to type
        :param wpm: Words per minute (approximate)
        :param error_rate: Probability of making an error per character (0.0 to 1.0).
        :param auto_tab: If True, performs Alt+Tab before typing.
        :param hesitation_prob: Probability of a mid-word pause ("travadinha").
        :param retry_rate: Probability of doing a "full retry" (simulating a bigger mistake).
        :param late_error_rate: Probability of making a mistake, typing 2-5 more chars, and then correcting.
        :param max_typos: Maximum number of standard typos allowed per word.
        :param max_late_errors: Maximum number of late mistakes allowed per word.
        :param return_tab: If True, performs Alt+Tab after typing.
        :param delayed_type: If True, types noise, presses enter, waits, then types the word very fast.
        :param add_period_prob: Probability of adding a period at the end of the word.
        """
        if self.is_typing:
            return
        
        self.is_typing = True
        
        kwargs = {
            'retry_rate': retry_rate,
            'late_error_rate': late_error_rate,
            'max_typos': max_typos,
            'max_late_errors': max_late_errors,
            'hesitation_prob': hesitation_prob,
            'return_tab': return_tab,
            'delayed_type': delayed_type,
            'add_period_prob': add_period_prob
        }
        
        t = threading.Thread(target=self._type_thread, args=(word, wpm, error_rate, auto_tab), kwargs=kwargs)
        t.start()

    def _type_thread(self, word, wpm, error_rate, auto_tab, retry_rate=0.0, late_error_rate=0.0, max_typos=2, max_late_errors=1, hesitation_prob=0.05, return_tab=False, delayed_type=False, add_period_prob=0.0):
        self._abort = False # Reseta a flag antes de começar a thread
        try:
            if auto_tab:
                # Alt + Tab to switch to the game window
                pyautogui.keyDown('alt')
                pyautogui.press('tab')
                pyautogui.keyUp('alt')
                time.sleep(0.15) # Slightly longer for focus stability
            
            if self._abort: return

            # Add period at the end based on probability
            if add_period_prob > 0 and random.random() < add_period_prob:
                word += '.'

            if delayed_type:
                # Spam noise for 0.5 to 1 second
                spam_duration = random.uniform(0.5, 1.0)
                spam_start = time.time()
                while time.time() - spam_start < spam_duration:
                    if self._abort: break
                    noise_len = random.randint(1, 4)
                    noise = "".join(random.choice("abcdefghijklmnopqrstuvwxyz") for _ in range(noise_len))
                    
                    # Moderate-speed burst of random characters (approx 400 WPM)
                    keyboard.write(noise, delay=0.03)
                    
                    time.sleep(random.uniform(0.05, 0.1))
                    pyautogui.press('enter')
                    time.sleep(random.uniform(0.1, 0.15))
                
                if self._abort: return
                
                # Type the actual word slower than the configured WPM
                slow_wpm = wpm * 0.75
                self._human_type(word, slow_wpm, error_rate, hesitation_prob, late_error_rate, max_typos, max_late_errors)
                
                if self._abort: return
                time.sleep(abs(random.gauss(0.1, 0.05)))
                pyautogui.press('enter')

            else:
                # Determine if we should do a "Full Retry"
                do_full_retry = False
                if retry_rate > 0 and random.random() < retry_rate:
                     do_full_retry = True

                if do_full_retry:
                    wrong_word = self._make_typo(word)
                    self._human_type(wrong_word, wpm, error_rate, hesitation_prob)
                    
                    if self._abort: return
                    
                    time.sleep(abs(random.gauss(0.2, 0.05)))
                    pyautogui.press('enter')
                    
                    if self._abort: return
                    
                    # Human realization "oh shit, I typed wrong"
                    time.sleep(abs(random.gauss(0.8, 0.2)))
                    
                    # Clear input field (Ctrl+A + Backspace) before retry
                    pyautogui.keyDown('ctrl')
                    pyautogui.press('a')
                    pyautogui.keyUp('ctrl')
                    time.sleep(0.05)
                    pyautogui.press('backspace')
                    time.sleep(0.12)
                    
                    # Retry faster and more careful
                    faster_wpm = wpm * random.uniform(1.2, 1.5)
                    lower_err = error_rate * 0.2
                    self._human_type(word, faster_wpm, lower_err, hesitation_prob * 0.5, late_error_rate=0.0, max_typos=1, max_late_errors=0)
                    time.sleep(abs(random.gauss(0.1, 0.05)))
                    pyautogui.press('enter')

                else:
                    self._human_type(word, wpm, error_rate, hesitation_prob, late_error_rate, max_typos, max_late_errors)
                    
                    if self._abort: return
                    
                    time.sleep(abs(random.gauss(0.1, 0.05)))
                    pyautogui.press('enter')

            if return_tab and not self._abort:
                # Alt + Tab to switch back to the manual interface (browser)
                time.sleep(0.1)
                pyautogui.keyDown('alt')
                pyautogui.press('tab')
                pyautogui.keyUp('alt')
                
        except Exception as e:
            print(f"Typing error: {e}")
        finally:
            self.is_typing = False
            self._abort = False

    def _get_typo_char(self, char):
        c_lower = char.lower()
        if c_lower in QWERTY_MAP:
            wrong_char = random.choice(QWERTY_MAP[c_lower])
            return wrong_char.upper() if char.isupper() else wrong_char
        return char

    def _human_type(self, word, wpm, error_rate, hesitation_prob=0.05, late_error_rate=0.0, max_typos=2, max_late_errors=1):
        chars_per_second = (wpm * 5) / 60
        base_delay = 1.0 / chars_per_second if chars_per_second > 0 else 0.1

        # Drift and Cluster mechanics
        current_speed_modifier = 1.0
        in_burst = False
        burst_chars_left = 0
        recovery_penalty = 0.0
        typos_made = 0
        late_errors_made = 0
        
        # Late mistake state
        late_mistake_active = False
        mistake_index = -1
        chars_typed_since_mistake = 0
        mistake_chars_limit = 0
        
        # Turbo Mode: If WPM is very high, we skip most "human-like" pauses to focus on speed
        turbo = wpm >= 180
        
        i = 0
        while i < len(word):
            if self._abort:
                break
                
            char = word[i]
            
            # --- 1. PRE-KEYSTROKE TIMING & CONTEXT ---
            if not turbo:
                # Contextual Pauses (before punctuation or capitals inside a word)
                if char in "'_" or (char.isupper() and i > 0 and word[i-1].islower()):
                    time.sleep(abs(random.gauss(0.2, 0.05)))
                    
                # Difficult letters slow down the specific keystroke
                if char.lower() in DIFFICULT_LETTERS:
                    time.sleep(abs(random.gauss(0.12, 0.04)))
                    in_burst = False # Break burst on difficult letters

                # Mute consonants
                if i < len(word) - 1:
                    c_lower = char.lower()
                    n_lower = word[i+1].lower()
                    if n_lower and c_lower in "bcdfgkptv" and n_lower in "bcdfghjklmnpqrstvwxyz":
                        if n_lower not in "rlh" and c_lower != n_lower:
                            time.sleep(abs(random.gauss(0.15, 0.04)))
                            in_burst = False
                
                # Mid-word hesitation / Loss of train of thought
                if i > 0 and random.random() < hesitation_prob:
                    time.sleep(abs(random.gauss(0.6, 0.2)))
                    in_burst = False

            # --- 2. BURST & SPEED CALCULATION ---
            if not in_burst and random.random() < 0.35: 
                in_burst = True
                burst_chars_left = random.randint(2, 5)
                current_speed_modifier = random.uniform(0.6, 0.85) 
            elif in_burst:
                burst_chars_left -= 1
                if burst_chars_left <= 0:
                    in_burst = False
                    current_speed_modifier = random.uniform(1.0, 1.3)
            else:
                drift = random.gauss(0, 0.15)
                current_speed_modifier = float(max(0.7, min(1.5, float(current_speed_modifier) + drift)))

            # Calculate final delay for this stroke
            delay = float(base_delay) * float(current_speed_modifier)
            if recovery_penalty > 0:
                delay *= (1.0 + float(recovery_penalty))
                recovery_penalty = max(0.0, float(recovery_penalty) - 0.15)
            
            variation = delay * (0.05 if turbo else 0.25)
            final_delay = abs(random.gauss(delay, variation))

            # --- 3. ERROR LOGIC & KEYSTROKE ---
            
            # 3.1 Normal Typo Correction (Immediate - Fat finger insertion or realistic substitution)
            # Only trigger Standard Typo if NOT in a Late Mistake to avoid chaos
            if not late_mistake_active and typos_made < max_typos and error_rate > 0 and random.random() < error_rate:
                typos_made += 1
                wrong_char = self._get_typo_char(char)
                
                # 70% chance to simulate fat-finger insertion (types correct then wrong immediately, deletes wrong)
                # 30% chance to simulate substitution (types wrong instead of correct, deletes wrong, types correct)
                if random.random() < 0.7:
                    keyboard.write(char)
                    time.sleep(random.uniform(0.01, 0.05))
                    keyboard.write(wrong_char)
                    
                    # Realization pause
                    time.sleep(max(0.12, abs(random.gauss(0.28, 0.08))))
                    keyboard.press_and_release('backspace')
                    
                    # Already typed correctly, so increment i and continue
                    i += 1
                else:
                    keyboard.write(wrong_char)
                    
                    # Realization pause
                    time.sleep(max(0.12, abs(random.gauss(0.28, 0.08))))
                    keyboard.press_and_release('backspace')
                    
                    # Do not increment i, will retry the same char on next loop iteration
                
                # Recovery pause
                time.sleep(abs(random.gauss(0.18, 0.05)))
                recovery_penalty = 0.35
                in_burst = False
                continue

            # 3.2 Late Mistake Trigger
            # Only trigger a Late Mistake if NOT already in one, and NOT currently doing a Normal Typo fix
            # Also don't trigger too close to the end.
            elif not late_mistake_active and late_errors_made < max_late_errors and late_error_rate > 0 and \
               random.random() < late_error_rate and i < len(word) - 4:
                
                late_errors_made += 1
                late_mistake_active = True
                mistake_index = i
                mistake_chars_limit = random.randint(2, 5)
                chars_typed_since_mistake = 0
                
                wrong_char = self._get_typo_char(char)
                keyboard.write(wrong_char)
                
                if final_delay > 0.001:
                    time.sleep(final_delay)
                
                i += 1
                continue # Skip normal typing for this index as we just typed the wrong char

            # 3.3 Keystroke Execution (Normal or Late Mistake Phase)
            if late_mistake_active:
                keyboard.write(char)
                chars_typed_since_mistake += 1
                
                if final_delay > 0.001:
                    time.sleep(final_delay)
                
                # Correction Logic: "Oh, wait, I messed up back there"
                if chars_typed_since_mistake >= mistake_chars_limit or i == len(word) - 1:
                    time.sleep(abs(random.gauss(0.45, 0.12))) # Realization pause
                    
                    to_delete = chars_typed_since_mistake + 1
                    for _ in range(to_delete):
                        keyboard.press_and_release('backspace')
                        time.sleep(random.uniform(0.04, 0.08))
                    
                    time.sleep(abs(random.gauss(0.3, 0.1))) # Safety pause
                    
                    late_mistake_active = False
                    i = mistake_index # Reset to the mistake index to type it correctly
                    current_speed_modifier = float(current_speed_modifier) * 0.75 # Small speed boost to "catch up"
                    continue
            else:
                # Normal Keystroke
                keyboard.write(char)
                if final_delay > 0.001:
                    time.sleep(final_delay)
            
            i += 1

    def _make_typo(self, word):
        # Create a realistic "wrong" version of the word for the full retry scenario
        if len(word) < 2:
            return word + self._get_typo_char(word[-1] if word else 'a')
        
        choice = random.choice(['skip', 'swap', 'wrong_char', 'double'])
        if choice == 'skip':
            idx = random.randint(0, len(word)-1)
            return word[:idx] + word[idx+1:]
        elif choice == 'swap':
            idx = random.randint(0, len(word)-2)
            return word[:idx] + word[idx+1] + word[idx] + word[idx+2:]
        elif choice == 'double':
            idx = random.randint(0, len(word)-1)
            return word[:idx] + word[idx] + word[idx] + word[idx+1:]
        else:
            # Replace a char with a proximity one
            idx = random.randint(0, len(word)-1)
            return word[:idx] + self._get_typo_char(word[idx]) + word[idx+1:]
