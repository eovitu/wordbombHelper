import tkinter as tk
from tkinter import font as tkfont

class OverlayApp:
    def __init__(self, update_region_callback):
        self.update_callback_func = update_region_callback
        
        # Window Setup
        self.root = tk.Tk()
        self.root.title("WordBomb Helper Area")
        self.root.geometry("300x150+100+100")  # Default size and pos
        self.root.attributes('-topmost', True)  # Always on top
        
        # Windows-specific: Make the background color (lime) completely transparent
        self.root.wm_attributes("-transparentcolor", "lime")
        self.root.configure(bg='lime')
        
        # A sleek, thin border to demarcate the capture area without being intrusive
        # Using a premium 'electric purple' instead of plain red
        self.border_frame = tk.Frame(self.root, bg='#8b5cf6', bd=2)
        self.border_frame.pack(fill='both', expand=True)
        
        # Inner container for the suggested word
        self.inner_frame = tk.Frame(self.border_frame, bg='lime')
        self.inner_frame.pack(fill='both', expand=True, padx=2, pady=2)
        
        # Premium Label Design
        # We use a container frame to give it a solid background that doesn't 
        # interfere with the lime transparency logic
        self.label_container = tk.Frame(self.inner_frame, bg='#1a1a1a', bd=0)
        self.label_container.place(relx=0.5, rely=0.8, anchor="s")
        
        # Word Label
        self.word_label = tk.Label(
            self.label_container, 
            text="", 
            font=("Space Grotesk", 28, "bold"), 
            fg="#ffffff", 
            bg="#1a1a1a",
            padx=20,
            pady=10
        )
        self.word_label.pack()
        
        # Status Label (small, below the word)
        self.status_label = tk.Label(
            self.inner_frame,
            text="ENGAGED",
            font=("Inter", 8, "bold"),
            fg="#8b5cf6",
            bg="#1a1a1a",
            padx=5
        )
        # self.status_label.place(relx=0.5, rely=0.82, anchor="n")
        
        # Start HIDDEN — only show when Auto-Play is activated
        self.root.withdraw()
        self._visible = False
        self._updating = False
        self._check_signals()

    def _check_signals(self):
        # Allow Python to process signals like KeyboardInterrupt (Ctrl+C)
        self.root.after(200, self._check_signals)

    def start(self):
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            self.root.destroy()

    def show(self):
        """Show the overlay and start position updates."""
        if not self._visible:
            self.root.deiconify()
            self._visible = True
            if not self._updating:
                self._updating = True
                self.root.after(200, self.update_position)

    def hide(self):
        """Hide the overlay and stop position updates."""
        if self._visible:
            self.root.withdraw()
            self._visible = False
            self._updating = False

    def update_position(self):
        if not self._visible:
            self._updating = False
            return
            
        try:
            x = self.root.winfo_rootx()
            y = self.root.winfo_rooty()
            w = self.root.winfo_width()
            h = self.root.winfo_height()
            
            region = {
                'x1': x,
                'y1': y,
                'width': w,
                'height': h
            }
            if self.update_callback_func:
                self.update_callback_func(region)
        except Exception:
            pass
            
        self.root.after(200, self.update_position)

    def set_word(self, word):
        """Update the displayed word in the overlay (Thread-safe)."""
        def _update():
            if hasattr(self, 'word_label'):
                text = word.upper() if word else ""
                self.word_label.config(text=text)
                
                # Dynamic sizing: if word is empty, hide the container
                if not text:
                    self.label_container.place_forget()
                else:
                    self.label_container.place(relx=0.5, rely=0.9, anchor="s")
        
        try:
            self.root.after(0, _update)
        except Exception:
            pass

# Global reference so main.py can show/hide
_overlay_instance = None

def run_overlay(callback):
    global _overlay_instance
    _overlay_instance = OverlayApp(callback)
    _overlay_instance.start()

def get_overlay():
    return _overlay_instance
