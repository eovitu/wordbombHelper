import random

# Mocking timing and keyboard to trace logical output
class MockKeyboard:
    def __init__(self):
        self.buffer = []
        self.history = []

    def write(self, char):
        self.buffer.append(char)
        self.history.append(f"WRITE: {char}")

    def press_and_release(self, key):
        if key == 'backspace':
            if self.buffer:
                removed = self.buffer.pop()
                self.history.append(f"BACKSPACE: removed {removed}")
            else:
                self.history.append("BACKSPACE: nothing to remove!")
        else:
            self.history.append(f"PRESS: {key}")

class Simulator:
    def __init__(self, error_rate=0.1, late_error_rate=0.1):
        self.keyboard = MockKeyboard()
        self.error_rate = error_rate
        self.late_error_rate = late_error_rate
        self.max_typos = 2
        self.max_late_errors = 1
        self._abort = False

    def _get_typo_char(self, char):
        return "X" # Simplified typo

    def simulate_human_type(self, word):
        typos_made = 0
        late_errors_made = 0
        late_mistake_active = False
        mistake_index = -1
        chars_typed_since_mistake = 0
        mistake_chars_limit = 0
        
        i = 0
        while i < len(word):
            char = word[i]
            
            # --- 3.1 Normal Typo ---
            if not late_mistake_active and typos_made < self.max_typos and self.error_rate > 0 and random.random() < self.error_rate:
                typos_made += 1
                wrong_char = self._get_typo_char(char)
                self.keyboard.write(wrong_char)
                self.keyboard.press_and_release('backspace')
                # Now the loop continues to the normal keystroke (if not late mistake)

            # --- 3.2 Late Mistake Trigger ---
            if late_errors_made < self.max_late_errors and not late_mistake_active and self.late_error_rate > 0 and random.random() < self.late_error_rate and i < len(word) - 4:
                late_errors_made += 1
                late_mistake_active = True
                mistake_index = i
                mistake_chars_limit = 3 
                chars_typed_since_mistake = 0
                
                wrong_char = self._get_typo_char(char)
                self.keyboard.write(wrong_char)
                i += 1
                continue

            # --- 3.3 Late Mistake Correction ---
            if late_mistake_active:
                self.keyboard.write(char)
                chars_typed_since_mistake += 1
                
                if chars_typed_since_mistake >= mistake_chars_limit or i == len(word) - 1:
                    to_delete = chars_typed_since_mistake + 1
                    for _ in range(to_delete):
                        self.keyboard.press_and_release('backspace')
                    
                    late_mistake_active = False
                    i = mistake_index
                    continue
            else:
                # --- 3.4 Normal Keystroke ---
                self.keyboard.write(char)
            
            i += 1
        
        return "".join(self.keyboard.buffer)

# Run simulations
sim = Simulator(error_rate=0.2, late_error_rate=0.4)
found_mistake = False
for _ in range(100):
    result = sim.simulate_human_type("stroopwafel")
    if result != "stroopwafel":
        print(f"CRITICAL ERROR: Logic produced {result}")
        for h in sim.keyboard.history:
              print(f"  {h}")
        break
    
    # Check if a late mistake actually happened in the history to show it
    if any("BACKSPACE: removed X" for h in sim.keyboard.history if "BACKSPACE: removed S" not in h):
        if not found_mistake:
            print("LOGICAL TRACE OF A SUCCESSFUL CORRECTION:")
            for h in sim.keyboard.history:
                print(f"  {h}")
            print(f"FINAL RESULT: {result}")
            found_mistake = True
            
    sim.keyboard.buffer = []
    sim.keyboard.history = []
