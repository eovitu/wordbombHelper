import time
import random
import pyautogui
import threading
import keyboard

# Fail-safe: Move mouse to upper-left corner to abort
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.001 # Minimize default pause between actions

# QWERTY Proximity Map for realistic typos
QWERTY_MAP = {
    'q': 'wa', 'w': 'qeasd', 'e': 'wrsfd', 'r': 'etdfg', 't': 'ryfgh', 'y': 'tughj', 'u': 'yihjk', 'i': 'uojkl', 'o': 'ipkl', 'p': 'ol',
    'a': 'qwsz', 's': 'qweadzx', 'd': 'wersfxc', 'f': 'ertdgcv', 'g': 'rtyfhvb', 'h': 'tyugjbn', 'j': 'yuihknm', 'k': 'uiojlm', 'l': 'iopk',
    'z': 'asx', 'x': 'zsdc', 'c': 'xdfv', 'v': 'cfgb', 'b': 'vghn', 'n': 'bhjm', 'm': 'njk',
    '-': '0p', '.': 'm,', ',': 'mn', ' ': 'vbnm',
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

    def type_word(self, word, wpm=60, error_rate=0.0, auto_tab=True, hesitation_prob=0.05, retry_rate=0.0, late_error_rate=0.0, max_typos=2, max_late_errors=1, return_tab=False):
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
            'return_tab': return_tab
        }
        
        t = threading.Thread(target=self._type_thread, args=(word, wpm, error_rate, auto_tab), kwargs=kwargs)
        t.start()

    def _type_thread(self, word, wpm, error_rate, auto_tab, retry_rate=0.0, late_error_rate=0.0, max_typos=2, max_late_errors=1, hesitation_prob=0.05, return_tab=False):
        try:
            if auto_tab:
                # Alt + Tab to switch to the game window
                pyautogui.keyDown('alt')
                pyautogui.press('tab')
                pyautogui.keyUp('alt')
                time.sleep(0.15) # Slightly longer for focus stability

            # Determine if we should do a "Full Retry"
            do_full_retry = False
            if retry_rate > 0 and random.random() < retry_rate:
                 do_full_retry = True

            if do_full_retry:
                wrong_word = self._make_typo(word)
                self._human_type(wrong_word, wpm, error_rate, hesitation_prob)
                time.sleep(abs(random.gauss(0.2, 0.05)))
                pyautogui.press('enter')
                
                # Human realization "oh shit, I typed wrong"
                time.sleep(abs(random.gauss(0.8, 0.2)))
                
                # Retry faster and more careful
                faster_wpm = wpm * random.uniform(1.2, 1.5)
                lower_err = error_rate * 0.2
                self._human_type(word, faster_wpm, lower_err, hesitation_prob * 0.5)
                time.sleep(abs(random.gauss(0.1, 0.05)))
                pyautogui.press('enter')

            else:
                self._human_type(word, wpm, error_rate, hesitation_prob, late_error_rate, max_typos, max_late_errors)
                time.sleep(abs(random.gauss(0.1, 0.05)))
                pyautogui.press('enter')

            if return_tab:
                # Alt + Tab to switch back to the manual interface (browser)
                time.sleep(0.1)
                pyautogui.keyDown('alt')
                pyautogui.press('tab')
                pyautogui.keyUp('alt')
                
        except Exception as e:
            print(f"Typing error: {e}")
        finally:
            self.is_typing = False

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
        
        i = 0
        while i < len(word):
            char = word[i]
            # 1. Contextual Pauses (before punctuation or capitals inside a word)
            if char in "'-_!?,." or (char.isupper() and i > 0 and word[i-1].islower()):
                time.sleep(abs(random.gauss(0.2, 0.05)))
                
            # Difficult letters slow down the specific keystroke
            if char.lower() in DIFFICULT_LETTERS:
                time.sleep(abs(random.gauss(0.12, 0.04)))
                in_burst = False # Break burst on difficult letters

            # Mute consonants (e.g. 'p' in 'hipnotizar', 'c' in 'hipocapnia')
            if i < len(word) - 1:
                c_lower = char.lower()
                n_lower = word[i+1].lower()
                if c_lower in "bcdfgkptv" and n_lower in "bcdfghjklmnpqrstvwxyz":
                    if n_lower not in "rlh" and c_lower != n_lower:
                        time.sleep(abs(random.gauss(0.15, 0.04)))
                        in_burst = False
            
            # Mid-word hesitation / Loss of train of thought
            if i > 0 and random.random() < hesitation_prob:
                time.sleep(abs(random.gauss(0.6, 0.2)))
                in_burst = False # Breaks the flow

            # 2. Burst Logic (Typing syllables/familiar patterns fast)
            if not in_burst and random.random() < 0.35: # 35% chance to start a fast cluster
                in_burst = True
                burst_chars_left = random.randint(2, 5)
                current_speed_modifier = random.uniform(0.6, 0.85) # Faster typing speed
            elif in_burst:
                burst_chars_left -= 1
                if burst_chars_left <= 0:
                    in_burst = False
                    current_speed_modifier = random.uniform(1.0, 1.3) # Slower transition after burst
            else:
                # Normal speed drift (random walk to simulate variable finger speed)
                drift = random.gauss(0, 0.15)
                current_speed_modifier = float(max(0.7, min(1.5, float(current_speed_modifier) + drift)))

            # 3. Handle Errors (Normal typos)
            if typos_made < max_typos and error_rate > 0 and random.random() < error_rate:
                typos_made += 1
                wrong_char = self._get_typo_char(char)
                keyboard.write(wrong_char)
                
                # Human reaction time to notice the error and press backspace
                reaction_time = abs(random.gauss(0.25, 0.08))
                time.sleep(max(0.1, reaction_time))
                keyboard.press_and_release('backspace')
                
                # Pause after deleting before typing the correct char
                time.sleep(abs(random.gauss(0.15, 0.05)))
                
                # Add a recovery penalty for the next few chars (brain refocusing)
                recovery_penalty = 0.35 
                in_burst = False # Errors break the typing burst

            # 4. Calculate final delay for this stroke
            delay = float(base_delay) * float(current_speed_modifier)
            if recovery_penalty > 0:
                delay *= (1.0 + float(recovery_penalty))
                # Decay the penalty over subsequent characters
                recovery_penalty = max(0.0, float(recovery_penalty) - 0.15)
            
            # Apply Gaussian variation for keystroke microscopic differences
            final_delay = abs(random.gauss(delay, delay * 0.25))
            
            if final_delay > 0.005:
                time.sleep(final_delay)
            
            # Trigger Late Mistake (only if not already in one and not at the very end)
            if late_errors_made < max_late_errors and not late_mistake_active and late_error_rate > 0 and random.random() < late_error_rate and i < len(word) - 4:
                late_errors_made += 1
                late_mistake_active = True
                mistake_index = i
                mistake_chars_limit = random.randint(2, 5)
                chars_typed_since_mistake = 0
                
                wrong_char = self._get_typo_char(char)
                keyboard.write(wrong_char)
                i += 1
                continue

            if late_mistake_active:
                keyboard.write(char)
                chars_typed_since_mistake += 1
                
                # If we reached the end of the mistake sequence or the word end
                if chars_typed_since_mistake >= mistake_chars_limit or i == len(word) - 1:
                    # Time to realize and correct
                    time.sleep(abs(random.gauss(0.4, 0.1))) # Realization pause
                    
                    # Backspace everything up to the mistake
                    to_delete = chars_typed_since_mistake + 1
                    for _ in range(to_delete):
                        keyboard.press_and_release('backspace')
                        time.sleep(random.uniform(0.03, 0.07))
                    
                    time.sleep(abs(random.gauss(0.3, 0.1))) # Extra safe pause after delete
                    
                    # Reset state and go back to the mistake index to type correctly
                    late_mistake_active = False
                    i = mistake_index
                    # Boost speed for correction
                    current_speed_modifier = float(current_speed_modifier) * 0.8
                    continue
            else:
                keyboard.write(char)
            
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
